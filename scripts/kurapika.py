#!/usr/bin/env python3
"""kurapika: per-topic notes for Claude Code, kept in a local Obsidian Vault.

Standard library only. Single CLI, dispatched via argparse subcommands.

Vault layout (only these three kinds of entries are managed):
    <vault>/index.md                     auto-generated list of topics
    <vault>/<topic>/summary.md           the one file to read for a topic
    <vault>/<topic>/ADR/ADR-0001-*.md    created on first use
    <vault>/<topic>/ISSUE/ISSUE-0001-*.md
    <vault>/knowledge/<topic>.md         digest of a closed topic
"""

import argparse
import contextlib
import datetime
import fcntl
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote

CONFIG_SCHEMA = "kurapika.config.v2"
ACCEPTED_SCHEMAS = ("kurapika.config.v1", CONFIG_SCHEMA)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PLUGIN_ROOT / "templates"

LANGS = ("ja", "en")
DEFAULT_LANG = "ja"

INDEX_NAME = "index.md"
INDEX_MARKER = "kurapika: index"
KNOWLEDGE_DIR = "knowledge"
SUMMARY_NAME = "summary.md"

STALE_DAYS = 30
ORGANIZE_INTERVAL_DAYS = 7
HOOK_TOPIC_LIMIT = 15
LONG_SECTION_LINES = 40

# Section key -> heading text per language. Headings in either language are
# recognised when reading, so switching language never orphans a section.
SECTIONS = {
    "oneline": {"ja": "一言で", "en": "Summary"},
    "now": {"ja": "現状 / 次にやること", "en": "Now / Next"},
    "direction": {"ja": "方針（仮）", "en": "Direction"},
    "research": {"ja": "調べたこと", "en": "Research"},
    "decisions": {"ja": "決めたこと", "en": "Decisions"},
    "issues": {"ja": "課題", "en": "Issues"},
    "history": {"ja": "経緯", "en": "History"},
}
APPEND_SECTIONS = ("research", "history")
REPLACE_SECTIONS = ("oneline", "now", "direction")
NOTE_SECTIONS = APPEND_SECTIONS + REPLACE_SECTIONS

STATUSES = {
    "active": {"ja": "進行中", "en": "active"},
    "paused": {"ja": "保留", "en": "paused"},
    "done": {"ja": "完了", "en": "done"},
}

MESSAGES = {
    "ja": {
        "not_configured": "Vault が未設定です。/obsidian-init で設定してください。",
        "vault_missing": "Vault が見つかりません: {path}",
        "topics_header": "進行中のトピック（{n}件）:",
        "no_topics": "進行中のトピックはありません。",
        "more": "…他 {n} 件",
        "cleaned": "片付け: 不要なファイル・空フォルダを {n} 件削除しました。",
        "index_conflict": "Vault の index.md は kurapika が作ったものではないため、更新していません。",
        "stale": "{days}日以上更新のないトピックが {n} 件あります。organize スキルで整理できます。",
        "organize_due": "前回の整理から{days}日以上経っています。organize スキルで整理できます。",
        "detail_hint": "詳細: kurapika topic show <トピック名>",
        "index_title": "トピック一覧",
        "index_note": "自動生成ファイルです。手で編集しないでください。",
        "index_topics": "トピック",
        "index_knowledge": "ナレッジ（閉じたトピック）",
        "none": "（なし）",
        "history_created": "トピックを作成",
        "history_replaced": "「{label}」を更新（旧: {old}）",
        "history_status": "状態を {old} → {new} に変更",
        "history_adr": "{label} を記録",
        "history_issue": "{label} を起票",
    },
    "en": {
        "not_configured": "Vault is not configured. Run /obsidian-init to set it up.",
        "vault_missing": "Vault path not found: {path}",
        "topics_header": "Active topics ({n}):",
        "no_topics": "No active topics.",
        "more": "...and {n} more",
        "cleaned": "Cleanup: removed {n} leftover file(s)/empty folder(s).",
        "index_conflict": "The Vault's index.md was not created by kurapika, so it was left untouched.",
        "stale": "{n} topic(s) have not been updated for {days}+ days. The organize skill can tidy them up.",
        "organize_due": "It has been {days}+ days since the last tidy-up. The organize skill can tidy things up.",
        "detail_hint": "Details: kurapika topic show <topic>",
        "index_title": "Topics",
        "index_note": "Auto-generated. Do not edit by hand.",
        "index_topics": "Topics",
        "index_knowledge": "Knowledge (closed topics)",
        "none": "(none)",
        "history_created": "Topic created",
        "history_replaced": "Updated \"{label}\" (was: {old})",
        "history_status": "Status changed: {old} -> {new}",
        "history_adr": "Recorded {label}",
        "history_issue": "Opened {label}",
    },
}

RESERVED_NAMES = {KNOWLEDGE_DIR.casefold(), INDEX_NAME.casefold()}
CLOSING_PREFIX = ".kurapika-closing-"

INVALID_NAME_RE = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]')
HEADING_RE = re.compile(r"^(#{1,6})\s")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
ADR_NUMBER_RE = re.compile(r"^ADR-(\d{4})-")
ISSUE_NUMBER_RE = re.compile(r"^ISSUE-(\d{4})-")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MD_LINK_RE = re.compile(r"\]\(([^)]+)\)")


class KurapikaError(Exception):
    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


# ---------- time ----------

def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.date.today().isoformat()


def days_since(iso_date: str) -> int:
    try:
        then = datetime.date.fromisoformat(iso_date[:10])
    except ValueError:
        return 0
    return (datetime.date.today() - then).days


# ---------- config / state ----------

def config_dir() -> Path:
    override = os.environ.get("KURAPIKA_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".config" / "kurapika"


def _read_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_config():
    data = _read_json(config_dir() / "config.json")
    if not data or data.get("schema") not in ACCEPTED_SCHEMAS or not data.get("vault_root"):
        return None
    if data.get("lang") not in LANGS:
        data["lang"] = DEFAULT_LANG
    return data


def save_config(**changes) -> dict:
    existing = load_config() or {}
    payload = {
        "schema": CONFIG_SCHEMA,
        "vault_root": existing.get("vault_root"),
        "lang": existing.get("lang", DEFAULT_LANG),
        "created": existing.get("created", now_iso()),
    }
    payload.update({k: v for k, v in changes.items() if v is not None})
    payload["updated"] = now_iso()
    _write_json(config_dir() / "config.json", payload)
    return payload


def load_state() -> dict:
    return _read_json(config_dir() / "state.json") or {}


def save_state(**changes):
    state = load_state()
    state.update(changes)
    _write_json(config_dir() / "state.json", state)


class Ctx:
    def __init__(self, root: Path, lang: str):
        self.root = root
        self.lang = lang

    def msg(self, key: str, **kwargs) -> str:
        return MESSAGES[self.lang][key].format(**kwargs)


def require_ctx() -> Ctx:
    cfg = load_config()
    if not cfg:
        raise KurapikaError("not_configured", MESSAGES[DEFAULT_LANG]["not_configured"])
    root = Path(cfg["vault_root"])
    if not root.is_dir():
        raise KurapikaError("vault_missing", MESSAGES[cfg["lang"]]["vault_missing"].format(path=root))
    return Ctx(root, cfg["lang"])


# ---------- file helpers ----------

def read_text(path: Path):
    """Text of a UTF-8 file, or None if it can't be read (missing, not UTF-8, ...)."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@contextlib.contextmanager
def vault_lock(timeout: float = 2.0):
    """Exclusive lock kept outside the Vault so no lock file litters it."""
    lock_path = config_dir() / "vault.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = open(lock_path, "a+")
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        yield acquired
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


@contextlib.contextmanager
def locked():
    with vault_lock() as acquired:
        if not acquired:
            raise KurapikaError("busy", "Another kurapika process is writing to the Vault. Try again.")
        yield


def safe_name(text: str, max_length: int = 80) -> str:
    """Folder/file name that keeps Japanese but drops path- and link-breaking characters."""
    name = INVALID_NAME_RE.sub("-", text.strip())
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-. ")
    return name[:max_length].rstrip("-. ")


def render_template(lang: str, name: str, **kwargs) -> str:
    text = (TEMPLATES_DIR / lang / name).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def obsidian_uri(path: Path) -> str:
    return "obsidian://open?path=" + quote(str(path.resolve()), safe="")


def link_alias(text: str) -> str:
    return text.replace("|", "/").replace("]", ")").replace("[", "(")


# ---------- front matter ----------

def _front_matter_end(lines: list):
    """Index of the closing '---', or None when there is no complete front matter."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    return None


def parse_front_matter(text: str) -> dict:
    lines = text.splitlines()
    end = _front_matter_end(lines)
    result = {}
    for line in lines[1:end] if end else []:
        key, sep, value = line.partition(":")
        if sep:
            result[key.strip()] = value.strip().strip('"')
    return result


def set_front_matter(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    end = _front_matter_end(lines)
    if end is None:
        lines = ["---", f"{key}: {value}", "---", ""] + lines
    else:
        for i in range(1, end):
            if lines[i].partition(":")[0].strip() == key:
                lines[i] = f"{key}: {value}"
                break
        else:
            lines.insert(end, f"{key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def first_heading(text: str):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


# ---------- sections ----------

def _fenced_mask(lines: list) -> list:
    """True for lines inside a code fence. An opener without a matching closer is
    plain text, so a stray ``` can never swallow the rest of the document."""
    mask = [False] * len(lines)
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if m:
            char, width = m.group(1)[0], len(m.group(1))
            for j in range(i + 1, len(lines)):
                s = lines[j].strip()
                if s and set(s) == {char} and len(s) >= width:
                    mask[i : j + 1] = [True] * (j + 1 - i)
                    i = j
                    break
        i += 1
    return mask


def _top_heading_level(line: str):
    """Level of a real ATX heading ('## x'), or None ('#tag' is not a heading)."""
    m = HEADING_RE.match(line.strip())
    return len(m.group(1)) if m else None


def _section_bounds(lines: list, key: str):
    variants = {"## " + h for h in SECTIONS[key].values()}
    mask = _fenced_mask(lines)
    start, end = None, len(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        if start is None:
            if line.strip() in variants:
                start = i
        else:
            level = _top_heading_level(line)
            if level is not None and level <= 2:
                end = i
                break
    return start, end


def demote_headings(body: str) -> str:
    """Turn '#'/'##' headings in user text into '###' so they can't split sections."""
    lines = body.splitlines()
    mask = _fenced_mask(lines)
    for i, line in enumerate(lines):
        level = _top_heading_level(line)
        if not mask[i] and level is not None and level <= 2:
            lines[i] = "###" + line.strip()[level:]
    return "\n".join(lines)


def get_section(text: str, key: str) -> str:
    lines = text.splitlines()
    start, end = _section_bounds(lines, key)
    if start is None:
        return ""
    return "\n".join(lines[start + 1 : end]).strip("\n")


def set_section(text: str, key: str, body: str, lang: str) -> str:
    lines = text.splitlines()
    start, end = _section_bounds(lines, key)
    body_lines = body.strip("\n").splitlines()
    block = [""] + body_lines + [""] if body_lines else [""]
    if start is None:
        lines = lines + ["", "## " + SECTIONS[key][lang]] + block
    else:
        lines = lines[: start + 1] + block + lines[end:]
    return "\n".join(lines).rstrip() + "\n"


def append_to_section(text: str, key: str, entry: str, lang: str) -> str:
    current = get_section(text, key)
    return set_section(text, key, f"{current}\n{entry}" if current else entry, lang)


def dated_entry(body: str) -> str:
    lines = body.strip("\n").splitlines()
    head = f"- {today()} {lines[0].strip()}"
    rest = ["  " + line if line.strip() else "" for line in lines[1:]]
    return "\n".join([head] + rest)


def parse_bullets(section: str) -> list:
    items = []
    for line in section.splitlines():
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif items and line.strip():
            items[-1] += "\n" + line.strip()
    return items


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------- topics ----------

def is_reserved(name: str) -> bool:
    return name.startswith(".") or name.casefold() in RESERVED_NAMES


def is_topic_dir(path: Path) -> bool:
    """Only real folders whose summary.md declares `type: topic` are kurapika's.
    Symlinks and the user's own folders are never treated as topics."""
    summary = path / SUMMARY_NAME
    if is_reserved(path.name) or path.is_symlink() or not path.is_dir():
        return False
    if summary.is_symlink() or not summary.is_file():
        return False
    text = read_text(summary)
    return text is not None and parse_front_matter(text).get("type") == "topic"


def topic_dirs(root: Path) -> list:
    return sorted(p for p in root.iterdir() if is_topic_dir(p))


def last_updated(topic: Path) -> str:
    mtimes = [p.stat().st_mtime for p in topic.rglob("*") if p.is_file()]
    stamp = max(mtimes) if mtimes else topic.stat().st_mtime
    return datetime.date.fromtimestamp(stamp).isoformat()


def resolve_topic(ctx: Ctx, name: str, partial: bool = False) -> Path:
    """Exact folder name first, then exact title. Substring matching only when
    `partial` is set, which is reserved for read-only lookups."""
    wanted = name.strip()
    if not wanted:
        raise KurapikaError("topic_not_found", "Topic name is empty.", candidates=[])
    topics = topic_dirs(ctx.root)
    key, key_safe = wanted.casefold(), safe_name(wanted).casefold()

    exact = [p for p in topics if p.name in (wanted, safe_name(wanted))]
    by_name = exact or [p for p in topics if p.name.casefold() in (key, key_safe)]
    if len(by_name) == 1:
        return by_name[0]
    titles = {p: (first_heading(read_summary(p)) or p.name) for p in topics}
    by_title = [p for p in topics if titles[p].strip().casefold() == key]
    if not by_name and len(by_title) == 1:
        return by_title[0]
    candidates = by_name or by_title
    if partial and not candidates:
        candidates = [p for p in topics if key in p.name.casefold() or key in titles[p].casefold()]
        if len(candidates) == 1:
            return candidates[0]
    raise KurapikaError(
        "topic_ambiguous" if candidates else "topic_not_found",
        f"Topic not found or ambiguous: {name}",
        candidates=[p.name for p in candidates],
    )


def read_summary(topic: Path) -> str:
    return (topic / SUMMARY_NAME).read_text(encoding="utf-8")


def numbered_docs(topic: Path, kind: str) -> list:
    pattern = ADR_NUMBER_RE if kind == "ADR" else ISSUE_NUMBER_RE
    folder = topic / kind
    if not folder.is_dir():
        return []
    docs = []
    for path in sorted(folder.glob(f"{kind}-*.md")):
        if not pattern.match(path.name):
            continue
        fm = parse_front_matter(read_text(path) or "")
        docs.append(
            {
                "file": path.name,
                "title": fm.get("title", path.stem),
                "status": fm.get("status", ""),
                "uri": obsidian_uri(path),
            }
        )
    return docs


def topic_info(ctx: Ctx, topic: Path, full: bool = False) -> dict:
    text = read_summary(topic)
    fm = parse_front_matter(text)
    status = fm.get("status", "active")
    history = parse_bullets(get_section(text, "history"))
    info = {
        "name": topic.name,
        "title": first_heading(text) or topic.name,
        "status": status,
        "status_label": STATUSES.get(status, {}).get(ctx.lang, status),
        "created": fm.get("created", ""),
        "updated": last_updated(topic),
        "oneline": get_section(text, "oneline"),
        "now": get_section(text, "now"),
        "uri": obsidian_uri(topic / SUMMARY_NAME),
    }
    if full:
        info.update(
            {
                "direction": get_section(text, "direction"),
                "history_recent": list(reversed(history))[:5],
                "history_total": len(history),
                "research_count": len(parse_bullets(get_section(text, "research"))),
                "adrs": numbered_docs(topic, "ADR"),
                "issues": numbered_docs(topic, "ISSUE"),
                "path": str(topic / SUMMARY_NAME),
            }
        )
    return info


def list_topics(ctx: Ctx) -> list:
    infos = [topic_info(ctx, p) for p in topic_dirs(ctx.root)]
    order = {"active": 0, "paused": 1, "done": 2}
    infos.sort(key=lambda t: t["updated"], reverse=True)
    infos.sort(key=lambda t: order.get(t["status"], 3))
    return infos


def write_summary(ctx: Ctx, topic: Path, text: str, history: str = None):
    if history:
        text = append_to_section(text, "history", dated_entry(history), ctx.lang)
    atomic_write_text(topic / SUMMARY_NAME, text)


def knowledge_dir(ctx: Ctx):
    """The knowledge/ folder if it is a real directory, else None."""
    path = ctx.root / KNOWLEDGE_DIR
    return path if path.is_dir() and not path.is_symlink() else None


# ---------- index ----------

def render_index(ctx: Ctx) -> str:
    lines = ["---", INDEX_MARKER, "---", "", f"# {ctx.msg('index_title')}", "", f"> {ctx.msg('index_note')}", ""]
    lines += [f"## {ctx.msg('index_topics')}", ""]
    topics = list_topics(ctx)
    for t in topics:
        entry = f"- [[{t['name']}/summary|{link_alias(t['title'])}]] — {t['status_label']} · {t['updated']}"
        oneline = first_line(t["oneline"])
        lines.append(f"{entry} — {shorten(oneline)}" if oneline else entry)
    if not topics:
        lines.append(f"- {ctx.msg('none')}")
    lines += ["", f"## {ctx.msg('index_knowledge')}", ""]
    knowledge = sorted(knowledge_dir(ctx).glob("*.md")) if knowledge_dir(ctx) else []
    for k in knowledge:
        if k.is_file():
            lines.append(f"- [[{KNOWLEDGE_DIR}/{k.stem}|{link_alias(k.stem)}]]")
    if not knowledge:
        lines.append(f"- {ctx.msg('none')}")
    return "\n".join(lines) + "\n"


def index_is_foreign(root: Path) -> bool:
    path = root / INDEX_NAME
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_file():
        return True
    text = read_text(path)
    return text is None or parse_front_matter(text).get("kurapika") != "index"


def write_index(ctx: Ctx) -> str:
    """Returns 'written', 'unchanged' or 'conflict' (a foreign index.md exists)."""
    if index_is_foreign(ctx.root):
        return "conflict"
    path = ctx.root / INDEX_NAME
    current = read_text(path)
    new = render_index(ctx)
    if new == current:
        return "unchanged"
    atomic_write_text(path, new)
    return "written"


# ---------- cleanup ----------

def run_cleanup(ctx: Ctx) -> dict:
    """Mechanical, always-safe tidy-up. Only touches what kurapika manages."""
    removed = []
    for leftover in (ctx.root / ".kurapika.lock", ctx.root / (INDEX_NAME + ".tmp")):
        if leftover.is_file():
            leftover.unlink()
            removed.append(leftover.name)
    for leftover in ctx.root.glob(CLOSING_PREFIX + "*"):
        if leftover.is_dir() and not leftover.is_symlink():
            shutil.rmtree(leftover, ignore_errors=True)
            removed.append(leftover.name + "/")
    managed = topic_dirs(ctx.root) + ([knowledge_dir(ctx)] if knowledge_dir(ctx) else [])
    for base in managed:
        for dirpath, _dirnames, filenames in os.walk(base, topdown=False):
            current = Path(dirpath)
            for filename in filenames:
                if filename.endswith((".md.bak", ".md.tmp")):
                    (current / filename).unlink()
                    removed.append(str((current / filename).relative_to(ctx.root)))
            if current != base and not any(current.iterdir()):
                current.rmdir()
                removed.append(str(current.relative_to(ctx.root)) + "/")
    return {"removed": removed, "index": write_index(ctx)}


# ---------- organize ----------

def obsidian_vault_root(root: Path) -> Path:
    """The enclosing Obsidian Vault (folder with .obsidian/), since wiki links
    resolve across the whole Vault even when kurapika lives in a subfolder."""
    for candidate in (root, *root.parents):
        if (candidate / ".obsidian").is_dir():
            return candidate
    return root


def _link_exists(target: str, files: set) -> bool:
    """Obsidian resolves [[a/b]] to any file whose path ends with a/b(.md)."""
    target = target.strip()
    for candidate in (target, target + ".md"):
        if candidate in files or any(f.endswith("/" + candidate) for f in files):
            return True
    return False


def organize_report(ctx: Ctx) -> dict:
    report = {
        "stale_topics": [],
        "long_sections": [],
        "broken_links": [],
        "folders_without_summary": [],
        "numbering_issues": [],
        "index": "ok",
    }
    for t in list_topics(ctx):
        age = days_since(t["updated"])
        if t["status"] != "done" and age >= STALE_DAYS:
            report["stale_topics"].append({"name": t["name"], "status": t["status"], "days": age})

    managed_files = []
    for topic in topic_dirs(ctx.root):
        text = read_summary(topic)
        for key in APPEND_SECTIONS:
            count = len(get_section(text, key).splitlines())
            if count > LONG_SECTION_LINES:
                report["long_sections"].append({"topic": topic.name, "section": key, "lines": count})
        for kind, pattern in (("ADR", ADR_NUMBER_RE), ("ISSUE", ISSUE_NUMBER_RE)):
            numbers = [
                int(m.group(1))
                for p in (topic / kind).glob(f"{kind}-*.md")
                for m in [pattern.match(p.name)]
                if m
            ] if (topic / kind).is_dir() else []
            dupes = sorted({n for n in numbers if numbers.count(n) > 1})
            missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers)) if numbers else []
            if dupes or missing:
                report["numbering_issues"].append(
                    {"topic": topic.name, "kind": kind, "duplicates": dupes, "missing": missing}
                )
        managed_files += list(topic.rglob("*.md"))
    if knowledge_dir(ctx):
        managed_files += list(knowledge_dir(ctx).glob("*.md"))
    if not index_is_foreign(ctx.root) and (ctx.root / INDEX_NAME).is_file():
        managed_files.append(ctx.root / INDEX_NAME)

    vault = obsidian_vault_root(ctx.root)
    files = {
        p.relative_to(vault).as_posix()
        for p in vault.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(vault).parts)
    }
    for path in managed_files:
        text = read_text(path)
        if text is None:
            continue
        for m in WIKI_LINK_RE.finditer(text):
            if not _link_exists(m.group(1), files):
                report["broken_links"].append({"file": str(path.relative_to(ctx.root)), "link": m.group(1)})
        for m in MD_LINK_RE.finditer(text):
            target = m.group(1).strip()
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                report["broken_links"].append({"file": str(path.relative_to(ctx.root)), "link": target})

    for p in sorted(ctx.root.iterdir()):
        if p.is_dir() and not p.name.startswith(".") and p.name != KNOWLEDGE_DIR and not is_topic_dir(p):
            report["folders_without_summary"].append(p.name)

    if index_is_foreign(ctx.root):
        report["index"] = "conflict"
    return report


# ---------- output ----------

def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def read_stdin_body() -> str:
    body = sys.stdin.read()
    if not body.strip():
        raise KurapikaError("empty_body", "Body (stdin) is empty.")
    return body


# ---------- commands: init / config ----------

def cmd_init(args):
    path = Path(args.path).expanduser().resolve()
    existed_before = path.exists()
    if not existed_before:
        if not args.create:
            raise KurapikaError("path_not_found", f"Path does not exist: {path}. Use --create to create it.")
        path.mkdir(parents=True)
    elif not path.is_dir():
        raise KurapikaError("not_a_directory", f"Not a directory: {path}")
    cfg = save_config(vault_root=str(path), lang=args.lang)
    if "last_organize" not in load_state():
        save_state(last_organize=now_iso())
    return emit(
        {
            "vault_root": str(path),
            "lang": cfg["lang"],
            "existed_before": existed_before,
            "looked_like_obsidian_vault": (path / ".obsidian").is_dir(),
        }
    )


def cmd_config_show(args):
    return emit(load_config() or {"vault_root": None})


def cmd_config_lang(args):
    if not load_config():
        raise KurapikaError("not_configured", MESSAGES[DEFAULT_LANG]["not_configured"])
    return emit(save_config(lang=args.lang))


# ---------- commands: hook ----------

def session_start_lines(ctx: Ctx) -> list:
    lines = []
    with vault_lock() as acquired:
        cleanup = run_cleanup(ctx) if acquired else {"removed": [], "index": "skipped"}
    topics = [t for t in list_topics(ctx) if t["status"] != "done"]

    if topics:
        lines.append(ctx.msg("topics_header", n=len(topics)))
        for t in topics[:HOOK_TOPIC_LIMIT]:
            label = t["title"] if t["title"] == t["name"] else f"{t['title']} [{t['name']}]"
            line = f"- {label}（{t['status_label']} / {t['updated']}）"
            details = [shorten(first_line(t[k]), 60) for k in ("oneline", "now") if first_line(t[k])]
            lines.append(line + (": " + " ｜ ".join(details) if details else ""))
        if len(topics) > HOOK_TOPIC_LIMIT:
            lines.append(ctx.msg("more", n=len(topics) - HOOK_TOPIC_LIMIT))
        lines.append(ctx.msg("detail_hint"))
    else:
        lines.append(ctx.msg("no_topics"))

    if cleanup["removed"]:
        lines.append(ctx.msg("cleaned", n=len(cleanup["removed"])))
    if cleanup["index"] == "conflict":
        lines.append(ctx.msg("index_conflict"))

    stale = [t for t in topics if days_since(t["updated"]) >= STALE_DAYS]
    if stale:
        lines.append(ctx.msg("stale", n=len(stale), days=STALE_DAYS))
    last = load_state().get("last_organize")
    if not last:
        save_state(last_organize=now_iso())
    elif topics and not stale and days_since(last) >= ORGANIZE_INTERVAL_DAYS:
        lines.append(ctx.msg("organize_due", days=ORGANIZE_INTERVAL_DAYS))
    return ["[kurapika] " + line if not line.startswith("- ") else line for line in lines]


def cmd_hook_session_start(args):
    # SessionStart must never block or break a session.
    try:
        cfg = load_config()
        if not cfg:
            print("[kurapika] " + MESSAGES[DEFAULT_LANG]["not_configured"])
            return 0
        root = Path(cfg["vault_root"])
        if not root.is_dir():
            print("[kurapika] " + MESSAGES[cfg["lang"]]["vault_missing"].format(path=root))
            return 0
        print("\n".join(session_start_lines(Ctx(root, cfg["lang"]))))
    except Exception:
        pass
    return 0


# ---------- commands: topic ----------

def cmd_topic_new(args):
    ctx = require_ctx()
    name = safe_name(args.title)
    if not name or is_reserved(name):
        raise KurapikaError("invalid_title", f"Cannot use this title as a folder name: {args.title}")
    topic = ctx.root / name
    with locked():
        # Compare case-insensitively: on macOS "Auth" and "auth" are the same folder.
        same = [p for p in ctx.root.iterdir() if p.name.casefold() == name.casefold()]
        existing = [p for p in same if is_topic_dir(p)]
        if existing:
            p = existing[0]
            return emit({"name": p.name, "created": False, "uri": obsidian_uri(p / SUMMARY_NAME)})
        if same:
            raise KurapikaError("folder_exists", f"A non-topic entry with this name already exists: {same[0].name}")
        text = render_template(ctx.lang, "summary.md", title=args.title.strip(), date=today())
        topic.mkdir(parents=True)
        write_summary(ctx, topic, text, history=ctx.msg("history_created"))
        write_index(ctx)
    return emit({"name": name, "created": True, "uri": obsidian_uri(topic / SUMMARY_NAME)})


def cmd_topic_list(args):
    ctx = require_ctx()
    topics = [t for t in list_topics(ctx) if t["status"] != "done"]
    for t in topics:
        t["oneline"] = first_line(t["oneline"])
        t["now"] = first_line(t["now"])
    return emit(topics)


def cmd_topic_show(args):
    ctx = require_ctx()
    return emit(topic_info(ctx, resolve_topic(ctx, args.name, partial=True), full=True))


def cmd_topic_status(args):
    ctx = require_ctx()
    topic = resolve_topic(ctx, args.name)
    with locked():
        text = read_summary(topic)
        old = parse_front_matter(text).get("status", "active")
        if old == args.status:
            return emit({"name": topic.name, "status": old, "changed": False})
        label = lambda s: STATUSES.get(s, {}).get(ctx.lang, s)  # noqa: E731
        text = set_front_matter(text, "status", args.status)
        write_summary(ctx, topic, text, history=ctx.msg("history_status", old=label(old), new=label(args.status)))
        write_index(ctx)
    return emit({"name": topic.name, "status": args.status, "changed": True})


def cmd_topic_close(args):
    ctx = require_ctx()
    topic = resolve_topic(ctx, args.name)
    knowledge = ctx.root / KNOWLEDGE_DIR
    if knowledge.is_symlink() or (knowledge.exists() and not knowledge.is_dir()):
        raise KurapikaError("knowledge_invalid", f"{KNOWLEDGE_DIR} must be a real folder inside the Vault.")
    files = sorted(str(p.relative_to(ctx.root)) for p in topic.rglob("*") if p.is_file())

    def free_target() -> Path:
        target, suffix = knowledge / f"{topic.name}.md", 2
        while target.exists() or target.is_symlink():
            target, suffix = knowledge / f"{topic.name}-{suffix}.md", suffix + 1
        return target

    if not args.confirm:
        target = free_target()
        return emit(
            {
                "would_delete": files,
                "knowledge_path": str(target.relative_to(ctx.root)),
                "hint": "pipe the knowledge body to stdin and add --confirm",
            }
        )
    body = read_stdin_body()
    text = read_summary(topic)
    content = render_template(
        ctx.lang,
        "knowledge.md",
        title=first_heading(text) or topic.name,
        created=parse_front_matter(text).get("created", ""),
        closed=today(),
        body=body.strip(),
    )
    with locked():
        # Move the folder aside first (atomic), so a failure never leaves a
        # half-deleted topic: on error it is put back; leftovers go in cleanup.
        staging = ctx.root / (CLOSING_PREFIX + topic.name)
        os.rename(topic, staging)
        try:
            target = free_target()
            atomic_write_text(target, content)
        except BaseException:
            os.rename(staging, topic)
            raise
        shutil.rmtree(staging, ignore_errors=True)
        write_index(ctx)
    return emit({"knowledge_path": str(target.relative_to(ctx.root)), "uri": obsidian_uri(target), "deleted": files})


# ---------- commands: note ----------

def cmd_note(args):
    ctx = require_ctx()
    topic = resolve_topic(ctx, args.topic)
    mode = "append" if args.section in APPEND_SECTIONS else "replace"
    body = demote_headings(read_stdin_body())
    with locked():
        text = read_summary(topic)
        history = None
        if mode == "append":
            text = append_to_section(text, args.section, dated_entry(body), ctx.lang)
        else:
            old = get_section(text, args.section)
            text = set_section(text, args.section, body, ctx.lang)
            if old.strip() and old.strip() != body.strip():
                label = SECTIONS[args.section][ctx.lang]
                history = ctx.msg("history_replaced", label=label, old=shorten(old, 60))
        write_summary(ctx, topic, text, history=history)
        write_index(ctx)
    return emit({"name": topic.name, "section": args.section, "mode": mode})


# ---------- commands: adr / issue ----------

def _next_number(folder: Path, pattern) -> int:
    numbers = [int(m.group(1)) for p in folder.glob("*.md") for m in [pattern.match(p.name)] if m] if folder.is_dir() else []
    return max(numbers, default=0) + 1


def _new_numbered_doc(ctx: Ctx, topic: Path, kind: str, title: str, template: str, list_section: str, history_key: str, **fields):
    pattern = ADR_NUMBER_RE if kind == "ADR" else ISSUE_NUMBER_RE
    folder = topic / kind
    number = f"{_next_number(folder, pattern):04d}"
    stem = f"{kind}-{number}-{safe_name(title, 50) or 'untitled'}"
    path = folder / f"{stem}.md"
    content = render_template(ctx.lang, template, number=number, title=title, topic=topic.name, date=today(), **fields)
    atomic_write_text(path, content)
    label = f"{kind}-{number}: {title}"
    text = read_summary(topic)
    text = append_to_section(text, list_section, f"- [[{topic.name}/{kind}/{stem}|{link_alias(label)}]]", ctx.lang)
    write_summary(ctx, topic, text, history=ctx.msg(history_key, label=label))
    write_index(ctx)
    return {"name": topic.name, "file": str(path.relative_to(ctx.root)), "path": str(path), "uri": obsidian_uri(path)}


def cmd_adr_new(args):
    ctx = require_ctx()
    topic = resolve_topic(ctx, args.topic)
    with locked():
        result = _new_numbered_doc(ctx, topic, "ADR", args.title, "adr.md", "decisions", "history_adr", status="accepted")
    return emit(result)


def cmd_issue_new(args):
    ctx = require_ctx()
    topic = resolve_topic(ctx, args.topic)
    refs = json.dumps([args.adr_ref] if args.adr_ref else [], ensure_ascii=False)
    with locked():
        result = _new_numbered_doc(
            ctx, topic, "ISSUE", args.title, "issue.md", "issues", "history_issue", status="open", adr_refs=refs
        )
    return emit(result)


# ---------- commands: search ----------

def _searchable_files(root: Path):
    for topic in topic_dirs(root):
        yield from (p for p in topic.rglob("*.md") if p.is_file())
    knowledge = root / KNOWLEDGE_DIR
    if knowledge.is_dir() and not knowledge.is_symlink():
        yield from sorted(knowledge.glob("*.md"))


def cmd_search(args):
    ctx = require_ctx()
    terms = [t for t in args.query.casefold().split() if t]
    if not terms:
        raise KurapikaError("empty_query", "Query is empty.")
    results = []
    for path in _searchable_files(ctx.root):
        text = read_text(path)
        if text is None:
            continue
        lowered = text.casefold()
        score = 0.0
        for term in terms:
            if term in path.stem.casefold():
                score += 10
            score += sum(5 for line in lowered.splitlines() if line.lstrip().startswith(("#", "title:")) and term in line)
            score += min(lowered.count(term), 20) * 0.5
        if score <= 0:
            continue
        snippets = [
            shorten(line.strip(), 120)
            for line in text.splitlines()
            if line.strip() and line.strip() != "---" and any(t in line.casefold() for t in terms)
        ][:2]
        rel = path.relative_to(ctx.root)
        results.append(
            {
                "topic": rel.parts[0] if rel.parts[0] != KNOWLEDGE_DIR else None,
                "kind": KNOWLEDGE_DIR if rel.parts[0] == KNOWLEDGE_DIR else (rel.parts[1] if len(rel.parts) > 2 else "summary"),
                "path": str(rel),
                "score": round(score, 1),
                "snippets": snippets,
                "uri": obsidian_uri(path),
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return emit(results[: 10])


# ---------- commands: organize ----------

def cmd_organize_report(args):
    ctx = require_ctx()
    report = organize_report(ctx)
    save_state(last_organize=now_iso())
    return emit(report)


# ---------- CLI wiring ----------

def build_arg_parser():
    parser = argparse.ArgumentParser(prog="kurapika")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Set the Vault root")
    p.add_argument("path")
    p.add_argument("--create", action="store_true")
    p.add_argument("--lang", choices=LANGS)
    p.set_defaults(func=cmd_init)

    config = sub.add_parser("config").add_subparsers(dest="config_command", required=True)
    config.add_parser("show").set_defaults(func=cmd_config_show)
    p = config.add_parser("lang")
    p.add_argument("lang", choices=LANGS)
    p.set_defaults(func=cmd_config_lang)

    hook = sub.add_parser("hook").add_subparsers(dest="hook_command", required=True)
    hook.add_parser("session-start").set_defaults(func=cmd_hook_session_start)

    topic = sub.add_parser("topic").add_subparsers(dest="topic_command", required=True)
    p = topic.add_parser("new")
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_topic_new)
    p = topic.add_parser("list")
    p.set_defaults(func=cmd_topic_list)
    p = topic.add_parser("show")
    p.add_argument("name")
    p.set_defaults(func=cmd_topic_show)
    p = topic.add_parser("status")
    p.add_argument("name")
    p.add_argument("status", choices=tuple(STATUSES))
    p.set_defaults(func=cmd_topic_status)
    p = topic.add_parser("close")
    p.add_argument("name")
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_topic_close)

    p = sub.add_parser("note", help="Write to a summary.md section (body from stdin)")
    p.add_argument("topic")
    p.add_argument("section", choices=NOTE_SECTIONS)
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("adr").add_subparsers(dest="adr_command", required=True).add_parser("new")
    p.add_argument("--topic", required=True)
    p.add_argument("--title", required=True)
    p.set_defaults(func=cmd_adr_new)

    p = sub.add_parser("issue").add_subparsers(dest="issue_command", required=True).add_parser("new")
    p.add_argument("--topic", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--adr-ref", default="", help="ADR filename, e.g. ADR-0001-xxx.md")
    p.set_defaults(func=cmd_issue_new)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.set_defaults(func=cmd_search)

    sub.add_parser("organize-report").set_defaults(func=cmd_organize_report)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        return args.func(args)
    except KurapikaError as e:
        print(json.dumps({"error": e.code, "message": e.message, **e.extra}, ensure_ascii=False), file=sys.stderr)
        return 1
    except OSError as e:
        print(json.dumps({"error": "os_error", "message": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
