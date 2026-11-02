<p align="center">
  <img src="assets/banner.svg" alt="kurapika" width="100%">
</p>

# kurapika

A Claude Code plugin that gives every task or topic one folder in a local Obsidian
Vault, with a single `summary.md` you can read to know where things stand. Claude
records research, the tentative direction, progress and decisions as you work, and
answers "what was that again?" with a summary, history and links.

> **Upgrading from 0.x:** 1.0 is a fresh start with a new Vault layout
> (topics instead of `<project>/TASKS/<feature>`). Old folders are not migrated;
> they are left untouched and reported by the organize skill.

## How it works

```
<vault>/
  index.md                      auto-generated list of topics (don't edit)
  <topic>/                      one folder per task or topic (Japanese names OK)
    summary.md                  the one file to read
    ADR/ADR-0001-<title>.md     decisions, created on first use
    ISSUE/ISSUE-0001-<title>.md trackable tasks, created on first use
  knowledge/<topic>.md          digest of a closed topic
```

`summary.md` has these sections:

| Section (ja / en)              | Written by     | Mode                                   |
| ------------------------------ | -------------- | -------------------------------------- |
| 一言で / Summary                | topic skill    | replace                                |
| 現状 / 次にやること / Now / Next | topic skill    | replace                                |
| 方針（仮） / Direction          | topic skill    | replace                                |
| 調べたこと / Research           | topic skill    | append, dated                          |
| 決めたこと / Decisions          | adr skill      | link list, automatic                   |
| 課題 / Issues                   | issue skill    | link list, automatic                   |
| 経緯 / History                  | all of them    | append, dated; replaced values go here |

- **Session start:** the hook runs the mechanical cleanup and gives Claude the
  list of active topics (one line each: summary and current status), so it knows
  the context before you say anything.
- **While working:** additions and updates to `summary.md` are written without
  asking (you get a one-line report). Creating a topic, an ADR or an issue is
  always confirmed first.
- **Recall:** ask "〇〇ってどうなってたっけ" and Claude answers with the summary,
  status, latest history and `obsidian://` links.
- **Closing:** `/topic-close` (or "このトピック閉じて") digests the topic
  (conclusion, decisions and why, lessons, reusable snippets) into `knowledge/`
  and deletes the folder.
- **Staying tidy:** only files people read are kept. No `.bak` files, the lock
  file lives in `~/.config/kurapika/`, and empty folders inside topics and
  `knowledge/` are removed at session start.

kurapika only manages its topic folders, `knowledge/` and `index.md`. It never
touches your other notes and won't overwrite an `index.md` it didn't create.

## Requirements

- **Python 3.9+**, standard library only. No extra install needed.
- **macOS or Linux** (the lock uses `fcntl`; Windows is not supported).
- **Claude Code CLI** with plugin support (`claude --version`).
- **Obsidian is optional.** The Vault is a plain Markdown folder; Obsidian is only
  needed to open the `obsidian://` links and browse the graph.

## Setup

```bash
git clone https://github.com/tomoki-nagasaka/kurapika.git
claude plugin marketplace add /path/to/kurapika
claude plugin install kurapika@kurapika-marketplace --scope user
```

Restart `claude`, then run `/obsidian-init` once. It asks for the Vault path (an
existing Obsidian Vault or a new folder) and the note language (`ja` default, or
`en`; change later with `kurapika config lang en`).

**Updating:** the installed copy is a cached snapshot refreshed only when the
version changes. After bumping `version` in `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace update kurapika-marketplace
claude plugin update kurapika@kurapika-marketplace
```

For quick local testing without installing, run `claude --plugin-dir /path/to/kurapika`.

## Skills

Every feature is a skill. Each one triggers from conversation and can also be run
by hand as `/<name>` (e.g. `/topic-close 認証`), except `obsidian-init`, which is
manual only.

| Skill           | Triggers on                                                                 | Does                                                                     |
| --------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `obsidian-init` | `/obsidian-init` only                                                       | first-time setup: Vault path and language                                |
| `topic`         | starting or resuming work, research findings, tentative plans, progress     | picks or creates the topic, updates `summary.md`                          |
| `adr`           | a decision is reached ("〜に決めた", "ADRにして")                              | creates an ADR after confirmation, links it from `summary.md`            |
| `issue`         | explicit request only ("issue作成", "ADRをissueに分解して")                    | creates issues, standalone or broken down from an ADR                    |
| `recall`        | "あれなんだっけ", "〇〇どうなってたっけ"                                      | summary, status, latest history and links                                |
| `organize`      | explicit request, or after the session-start suggestion                     | proposes fixes for stale topics, long notes, broken links; applies on OK |
| `topic-close`   | "このトピック閉じて", or agreeing to a close suggestion                        | digests the topic into `knowledge/` and deletes its folder, after confirmation |

Mechanical upkeep runs automatically in the SessionStart hook. It also suggests the
organize skill when a topic has had no updates for 30+ days, or otherwise when there
are active topics and it has been 7+ days since the last tidy-up.

## CLI (`kurapika`)

Skills call `kurapika` (`bin/kurapika`, on PATH inside Claude Code);
the hook runs `scripts/kurapika.py` directly. Output is JSON;
errors go to stderr as `{"error": ..., "message": ...}` with exit code 1.

| Command                                                   | Does                                                              |
| --------------------------------------------------------- | ----------------------------------------------------------------- |
| `init <path> [--create] [--lang ja\|en]`                  | sets the Vault root (and language)                                |
| `config show` / `config lang ja\|en`                      | shows / changes the setting                                       |
| `topic new --title T`                                     | creates `<T>/summary.md`                                          |
| `topic list`                                              | lists topics that are not done                                    |
| `topic show NAME`                                         | summary, status, latest 5 history entries, ADRs, issues, links    |
| `topic status NAME active\|paused\|done`                  | changes the status (logged to history)                            |
| `topic close NAME [--confirm]`                            | previews, or writes the stdin digest to `knowledge/` and deletes  |
| `note TOPIC SECTION`                                      | writes stdin to a section (`research`/`history` append, others replace) |
| `adr new --topic T --title A`                             | creates the next ADR and links it                                 |
| `issue new --topic T --title I [--adr-ref F]`             | creates the next issue and links it                               |
| `search QUERY`                                            | multi-word search over topics and `knowledge/` (top 10, with snippets) |
| `organize-report`                                         | report for the organize skill                                     |
| `hook session-start`                                      | mechanical cleanup + `index.md` + active topic list (the hook)    |

Topics are matched by exact folder name, then exact title. Only the read-only
`topic show` also accepts a unique partial match (`kurapika topic show 認証`);
commands that write or delete always need the exact name.

## Configuration

Stored per user in `~/.config/kurapika/` (`config.json`, `state.json`,
`vault.lock`). Set `KURAPIKA_CONFIG_DIR` to use another location.

## Development

```bash
python3 -m unittest discover -s tests
```

## Uninstalling

```bash
claude plugin uninstall kurapika@kurapika-marketplace
claude plugin marketplace remove kurapika-marketplace
```

Neither touches your Vault. Delete `~/.config/kurapika/` to clear the setting as
well.
