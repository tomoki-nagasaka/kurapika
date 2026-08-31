#!/usr/bin/env python3
"""kurapika: personal Obsidian vault manager for Claude Code.

Standard library only. Single CLI, dispatched via argparse subcommands.
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

CONFIG_DIR = Path.home() / ".config" / "kurapika"
CONFIG_PATH = CONFIG_DIR / "config.json"
CONFIG_SCHEMA = "kurapika.config.v1"

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PLUGIN_ROOT / "templates"

ADR_NUMBER_RE = re.compile(r"^ADR-(\d{4})-")
ISSUE_NUMBER_RE = re.compile(r"^ISSUE-(\d{4})-")
SLUG_INVALID_RE = re.compile(r"[^a-z0-9-]+")
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.date.today().isoformat()


# ---------- config ----------

def load_config():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != CONFIG_SCHEMA:
        return None
    if not data.get("vault_root"):
        return None
    return data


def save_config(vault_root: Path) -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = load_config()
    payload = {
        "schema": CONFIG_SCHEMA,
        "vault_root": str(vault_root),
        "created": existing["created"] if existing else now_iso(),
        "updated": now_iso(),
    }
    atomic_write_text(CONFIG_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def get_vault_root():
    cfg = load_config()
    if not cfg:
        return None
    return Path(cfg["vault_root"])


# ---------- generic helpers ----------

def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def backup_before_write(path: Path):
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


@contextlib.contextmanager
def with_lock(vault_root: Path, timeout: float = 2.0):
    """Best-effort exclusive lock on the vault. Fails open on timeout."""
    lock_path = vault_root / ".kurapika.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "a+")
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(0.05)
        yield acquired
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        fd.close()


def slugify(text: str, max_length: int = 60) -> str:
    text = text.strip().lower()
    text = SLUG_INVALID_RE.sub("-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = text.strip("-.")
    if not text:
        text = "untitled"
    return text[:max_length].rstrip("-")


def render_template(name: str, **kwargs) -> str:
    text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


# ---------- project / vault skeleton ----------

def resolve_project_name(project_dir: str) -> str:
    return Path(project_dir).resolve().name


def ensure_project_skeleton(vault_root: Path, project_name: str) -> list:
    created = []
    project_dir = vault_root / project_name
    tasks_dir = project_dir / "TASKS"
    summary_todo = project_dir / "summary-todo.md"

    if not project_dir.exists():
        project_dir.mkdir(parents=True)
        created.append(str(project_dir))

    if not tasks_dir.exists():
        tasks_dir.mkdir(parents=True)
        created.append(str(tasks_dir))

    if not summary_todo.exists():
        content = render_template(
            "summary-todo.md",
            project_name=project_name,
            created_date=today(),
        )
        atomic_write_text(summary_todo, content)
        created.append(str(summary_todo))

    return created


def feature_dir(vault_root: Path, project_name: str, feature_slug: str) -> Path:
    return vault_root / project_name / "TASKS" / feature_slug


def ensure_feature_skeleton(
    vault_root: Path, project_name: str, feature_slug: str, feature_title: str
):
    """Create the feature folder and summary.md if missing, and link it from
    summary-todo.md the first time. Returns (feature_dir, is_new_feature)."""
    fdir = feature_dir(vault_root, project_name, feature_slug)
    summary_path = fdir / "summary.md"
    is_new_feature = not fdir.exists()

    fdir.mkdir(parents=True, exist_ok=True)

    if not summary_path.exists():
        content = render_template(
            "feature-summary.md",
            project_name=project_name,
            feature_title=feature_title,
            created_date=today(),
        )
        atomic_write_text(summary_path, content)

    if is_new_feature:
        summary_todo_path = vault_root / project_name / "summary-todo.md"
        _upsert_link_line(
            summary_todo_path,
            "## In-progress features",
            f"- [{feature_title}](./TASKS/{feature_slug}/summary.md)",
        )

    return fdir, is_new_feature


def next_numbered_file(dir_path: Path, pattern: re.Pattern) -> int:
    if not dir_path.exists():
        return 1
    max_n = 0
    for entry in dir_path.iterdir():
        m = pattern.match(entry.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


# ---------- section / link upsert ----------

def _section_bounds(lines: list, heading: str):
    heading_level = len(heading) - len(heading.lstrip("#"))
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == heading.strip():
            start = i
            continue
        if start is not None:
            stripped = line.strip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                if level <= heading_level:
                    end = i
                    break
    return start, end


def upsert_section(text: str, heading: str, body: str) -> str:
    lines = text.splitlines()
    start, end = _section_bounds(lines, heading)
    body_lines = body.rstrip("\n").splitlines()
    if start is None:
        new_lines = lines + ["", heading, ""] + body_lines
    else:
        new_lines = lines[: start + 1] + [""] + body_lines + [""] + lines[end:]
    return "\n".join(new_lines).rstrip() + "\n"


def _append_line_in_section(text: str, heading: str, line: str) -> str:
    lines = text.splitlines()
    start, end = _section_bounds(lines, heading)
    if start is None:
        lines += ["", heading, "", line]
        return "\n".join(lines).rstrip() + "\n"
    section_lines = lines[start + 1 : end]
    if any(l.strip() == line.strip() for l in section_lines):
        return "\n".join(lines).rstrip() + "\n"
    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines[insert_at:insert_at] = [line]
    return "\n".join(lines).rstrip() + "\n"


def _upsert_link_line(path: Path, heading: str, line: str):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    backup_before_write(path)
    new_text = _append_line_in_section(text, heading, line)
    atomic_write_text(path, new_text)


# ---------- commands: init / config ----------

def cmd_init(args):
    path = Path(args.path).expanduser().resolve()
    existed_before = path.exists()
    if not existed_before:
        if not args.create:
            print(
                f"Path does not exist: {path}\nUse --create to create it.",
                file=sys.stderr,
            )
            return 1
        path.mkdir(parents=True)
    elif not path.is_dir():
        print(f"Not a directory: {path}", file=sys.stderr)
        return 1

    looked_like_obsidian_vault = (path / ".obsidian").is_dir()
    save_config(path)

    result = {
        "vault_root": str(path),
        "existed_before": existed_before,
        "looked_like_obsidian_vault": looked_like_obsidian_vault,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_config_show(args):
    cfg = load_config()
    print(json.dumps(cfg or {"vault_root": None}, ensure_ascii=False))
    return 0


def cmd_config_clear(args):
    cfg = load_config()
    if not cfg:
        print(json.dumps({"cleared": False, "reason": "not_configured"}, ensure_ascii=False))
        return 0
    if not args.confirm:
        print(json.dumps({"would_clear": cfg, "hint": "add --confirm to actually clear"}, ensure_ascii=False))
        return 0
    CONFIG_PATH.unlink()
    print(json.dumps({"cleared": True, "previous_vault_root": cfg["vault_root"]}, ensure_ascii=False))
    return 0


# ---------- commands: reset-project ----------

def cmd_reset_project(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    project_dir = vault_root / args.project
    if not project_dir.exists():
        print(json.dumps({"exists": False, "project": args.project}, ensure_ascii=False))
        return 0

    file_count = sum(1 for p in project_dir.glob("**/*") if p.is_file())

    if not args.confirm:
        print(
            json.dumps(
                {
                    "would_move": str(project_dir),
                    "file_count": file_count,
                    "hint": "add --confirm to actually move it into .trash",
                },
                ensure_ascii=False,
            )
        )
        return 0

    trash_dir = vault_root / ".trash"
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    dest = trash_dir / f"{args.project}-{timestamp}"

    with with_lock(vault_root):
        trash_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(project_dir), str(dest))

    print(json.dumps({"moved_to": str(dest), "file_count": file_count}, ensure_ascii=False))
    return 0


# ---------- commands: hook ----------

def cmd_hook_session_start(args):
    try:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        cfg = load_config()
        if not cfg:
            print("[kurapika] Vault is not configured. Run /obsidian-init to set it up.")
            return 0
        vault_root = Path(cfg["vault_root"])
        if not vault_root.is_dir():
            print(f"[kurapika] Vault path not found: {vault_root}")
            return 0
        project_name = resolve_project_name(project_dir)
        if not project_name or project_name == vault_root.name:
            return 0
        with with_lock(vault_root):
            created = ensure_project_skeleton(vault_root, project_name)
        if created:
            print(f"[kurapika] Created folder for {project_name}")
    except Exception:
        # SessionStart must never block a session on unexpected errors.
        pass
    return 0


# ---------- commands: feature ----------

def cmd_new_feature(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    feature_slug = slugify(args.feature_slug)

    with with_lock(vault_root):
        ensure_project_skeleton(vault_root, args.project)
        fdir, is_new_feature = ensure_feature_skeleton(
            vault_root, args.project, feature_slug, args.feature_title
        )

    result = {
        "project": args.project,
        "feature_slug": feature_slug,
        "feature_dir": str(fdir.relative_to(vault_root)),
        "is_new_feature": is_new_feature,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------- commands: ADR ----------

def cmd_new_adr(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    feature_slug = slugify(args.feature_slug)

    with with_lock(vault_root):
        ensure_project_skeleton(vault_root, args.project)
        fdir, is_new_feature = ensure_feature_skeleton(
            vault_root, args.project, feature_slug, args.feature_title
        )

        adr_dir = fdir / "ADR"
        adr_dir.mkdir(parents=True, exist_ok=True)

        number = next_numbered_file(adr_dir, ADR_NUMBER_RE)
        adr_slug = slugify(args.adr_slug)
        filename = f"ADR-{number:04d}-{adr_slug}.md"
        adr_path = adr_dir / filename

        content = render_template(
            "adr.md",
            number=f"{number:04d}",
            title=args.adr_title,
            status=args.status,
            project_name=args.project,
            feature_slug=feature_slug,
            date=today(),
        )
        atomic_write_text(adr_path, content)

        summary_path = fdir / "summary.md"
        _upsert_link_line(
            summary_path,
            "## Related ADRs",
            f"- [ADR-{number:04d}: {args.adr_title}](./ADR/{filename})",
        )

    result = {
        "project": args.project,
        "feature_slug": feature_slug,
        "adr_path": str(adr_path.relative_to(vault_root)),
        "is_new_feature": is_new_feature,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------- commands: issue ----------

def cmd_new_issue(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    feature_slug = slugify(args.feature_slug)
    fdir = feature_dir(vault_root, args.project, feature_slug)

    if not fdir.exists():
        print(
            json.dumps(
                {"error": "feature_not_found", "feature_slug": feature_slug},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    issue_dir = fdir / "ISSUE"

    with with_lock(vault_root):
        issue_dir.mkdir(parents=True, exist_ok=True)

        number = next_numbered_file(issue_dir, ISSUE_NUMBER_RE)
        issue_slug = slugify(args.issue_slug)
        filename = f"ISSUE-{number:04d}-{issue_slug}.md"
        issue_path = issue_dir / filename

        content = render_template(
            "issue.md",
            number=f"{number:04d}",
            title=args.issue_title,
            status=args.status,
            project_name=args.project,
            feature_slug=feature_slug,
            adr_refs=json.dumps([args.adr_ref] if args.adr_ref else []),
            date=today(),
        )
        atomic_write_text(issue_path, content)

    result = {
        "project": args.project,
        "feature_slug": feature_slug,
        "issue_path": str(issue_path.relative_to(vault_root)),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------- commands: update-doc ----------

def cmd_update_doc(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    path = Path(args.path)
    if not path.is_absolute():
        path = vault_root / path

    body = sys.stdin.read()

    with with_lock(vault_root):
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        backup_before_write(path)
        new_text = upsert_section(text, args.heading, body)
        atomic_write_text(path, new_text)

    print(json.dumps({"path": str(path)}, ensure_ascii=False))
    return 0


# ---------- commands: search ----------

def _iter_markdown_files(vault_root: Path, project: str = None):
    base = (vault_root / project) if project else vault_root
    if not base.exists():
        return
    for path in base.glob("**/*.md"):
        if path.is_file():
            yield path


def _score_file(path: Path, query: str) -> float:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0.0
    query_lower = query.lower()
    score = 0.0
    if query_lower in path.stem.lower():
        score += 10.0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and query_lower in stripped.lower():
            score += 5.0
        elif stripped.lower().startswith("title:") and query_lower in stripped.lower():
            score += 5.0
    occurrences = text.lower().count(query_lower)
    score += min(occurrences, 20) * 0.5
    return score


def cmd_search(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    results = []
    for path in _iter_markdown_files(vault_root, args.project):
        score = _score_file(path, args.query)
        if score > 0:
            results.append((score, path))
    results.sort(key=lambda t: t[0], reverse=True)

    output = [
        {"path": str(p.relative_to(vault_root)), "score": round(s, 2)}
        for s, p in results[: args.limit]
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


# ---------- commands: organize-report ----------

def _check_project(vault_root: Path, project_dir: Path) -> dict:
    issues = {
        "empty_features": [],
        "orphan_features": [],
        "adr_number_issues": [],
        "broken_links": [],
    }
    tasks_dir = project_dir / "TASKS"
    summary_todo = project_dir / "summary-todo.md"
    todo_text = summary_todo.read_text(encoding="utf-8") if summary_todo.exists() else ""

    if tasks_dir.exists():
        for fdir in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
            summary_path = fdir / "summary.md"
            adr_dir = fdir / "ADR"
            adr_files = sorted(adr_dir.glob("ADR-*.md")) if adr_dir.exists() else []

            if not summary_path.exists() and not adr_files:
                issues["empty_features"].append(str(fdir.relative_to(vault_root)))

            expected_link = f"TASKS/{fdir.name}/summary.md"
            if expected_link not in todo_text:
                issues["orphan_features"].append(str(fdir.relative_to(vault_root)))

            numbers = []
            for f in adr_files:
                m = ADR_NUMBER_RE.match(f.name)
                if m:
                    numbers.append(int(m.group(1)))
            seen = set()
            dupes = set()
            for n in numbers:
                if n in seen:
                    dupes.add(n)
                seen.add(n)
            if dupes:
                issues["adr_number_issues"].append(
                    {"feature": fdir.name, "duplicates": sorted(dupes)}
                )
            if numbers:
                missing = sorted(set(range(1, max(numbers) + 1)) - seen)
                if missing:
                    issues["adr_number_issues"].append(
                        {"feature": fdir.name, "missing": missing}
                    )

    for md_path in project_dir.glob("**/*.md"):
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (md_path.parent / target).resolve()
            if not resolved.exists():
                issues["broken_links"].append(
                    {"file": str(md_path.relative_to(vault_root)), "link": target}
                )

    return issues


def cmd_organize_report(args):
    vault_root = get_vault_root()
    if vault_root is None:
        print("Vault is not configured. Run /obsidian-init to set it up.", file=sys.stderr)
        return 1

    if args.project:
        project_dirs = [vault_root / args.project]
    else:
        project_dirs = [
            p for p in vault_root.iterdir() if p.is_dir() and not p.name.startswith(".")
        ]

    report = {}
    for project_dir in project_dirs:
        if project_dir.exists():
            report[project_dir.name] = _check_project(vault_root, project_dir)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


# ---------- CLI wiring ----------

def build_arg_parser():
    parser = argparse.ArgumentParser(prog="kurapika.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("path")
    p_init.add_argument("--create", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_config = sub.add_parser("config")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show").set_defaults(func=cmd_config_show)
    p_config_clear = config_sub.add_parser("clear")
    p_config_clear.add_argument("--confirm", action="store_true")
    p_config_clear.set_defaults(func=cmd_config_clear)

    p_reset_project = sub.add_parser("reset-project")
    p_reset_project.add_argument("--project", required=True)
    p_reset_project.add_argument("--confirm", action="store_true")
    p_reset_project.set_defaults(func=cmd_reset_project)

    p_hook = sub.add_parser("hook")
    hook_sub = p_hook.add_subparsers(dest="hook_command", required=True)
    hook_sub.add_parser("session-start").set_defaults(func=cmd_hook_session_start)

    p_feature = sub.add_parser("new-feature")
    p_feature.add_argument("--project", required=True)
    p_feature.add_argument("--feature-slug", required=True, help="English kebab-case")
    p_feature.add_argument("--feature-title", required=True, help="Human-facing title")
    p_feature.set_defaults(func=cmd_new_feature)

    p_adr = sub.add_parser("new-adr")
    p_adr.add_argument("--project", required=True)
    p_adr.add_argument("--feature-slug", required=True, help="English kebab-case")
    p_adr.add_argument("--feature-title", required=True, help="Human-facing title")
    p_adr.add_argument("--adr-slug", required=True, help="English kebab-case")
    p_adr.add_argument("--adr-title", required=True, help="Human-facing title")
    p_adr.add_argument("--status", default="proposed")
    p_adr.set_defaults(func=cmd_new_adr)

    p_issue = sub.add_parser("new-issue")
    p_issue.add_argument("--project", required=True)
    p_issue.add_argument("--feature-slug", required=True)
    p_issue.add_argument("--issue-slug", required=True, help="English kebab-case")
    p_issue.add_argument("--issue-title", required=True, help="Human-facing title")
    p_issue.add_argument(
        "--adr-ref", default="", help="Filename of the related ADR, e.g. ADR-0001-slug.md"
    )
    p_issue.add_argument("--status", default="open")
    p_issue.set_defaults(func=cmd_new_issue)

    p_update = sub.add_parser("update-doc")
    p_update.add_argument("--path", required=True, help="Path relative to vault_root, or absolute")
    p_update.add_argument("--heading", required=True, help='e.g. "## Overview" (body is read from stdin)')
    p_update.set_defaults(func=cmd_update_doc)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--project")
    p_search.add_argument("--limit", type=int, default=15)
    p_search.set_defaults(func=cmd_search)

    p_organize = sub.add_parser("organize-report")
    p_organize.add_argument("--project")
    p_organize.set_defaults(func=cmd_organize_report)

    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
