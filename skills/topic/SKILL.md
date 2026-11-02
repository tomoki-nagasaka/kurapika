---
name: topic
description: >-
  Keeps a per-topic note (summary.md) in the user's Obsidian Vault up to date:
  picks or creates the topic for the current work, and records research notes,
  the tentative direction, the current status / next step, and what was done.
  Use it when the user starts or resumes a task ("〇〇やる", "〇〇の続き",
  "let's work on X"), when research findings come up ("調べたら〜だった",
  "メモしておいて"), when a tentative direction is discussed ("方針としては〜"),
  or when a chunk of work finishes ("ここまでできた", "次は〜"). Not for final
  decisions (use the adr skill) or trackable tasks (use the issue skill).
---

# topic skill

Every task or subject gets one folder in the Vault, and its `summary.md` is the
single file to read to understand it. This skill keeps that file current.

All commands below use the `kurapika` CLI (on PATH via this plugin's `bin/`) and
print JSON. If a command fails with `not_configured`, ask the user to run
`/obsidian-init` and stop.

## 1. Pick the topic

- The SessionStart hook already put the list of active topics in your context.
  Run `kurapika topic list` if you need it again.
- If the work clearly belongs to one of them, use it silently.
- If it's ambiguous, ask which one (show 2-3 candidates).
- If it's new, propose a short title (Japanese is fine) and **ask before creating**:
  `kurapika topic new --title "<title>"`.
  Then fill `oneline` right away (one sentence: what this topic is about).

## 2. Write to summary.md

Pipe the body on stdin: `printf '%s\n' "<body>" | kurapika note "<topic>" <section>`

| Section     | Mode    | When                                                            |
| ----------- | ------- | --------------------------------------------------------------- |
| `oneline`   | replace | One sentence describing the topic. Rarely changes               |
| `now`       | replace | Current state and the next step. Update as work progresses      |
| `direction` | replace | Tentative approach, not yet a decision                          |
| `research`  | append  | Findings, references, commands that worked. Auto-dated          |
| `history`   | append  | What was done, one line per meaningful step. Auto-dated         |

- No confirmation is needed for these writes; after writing, tell the user in one
  short line what you recorded (e.g. "調べたことに追記しました").
- Replacing `oneline` / `now` / `direction` automatically logs the previous value to
  `history`, so don't log that yourself.
- Keep entries short and concrete: what, why, and links/commands. Don't paste long
  transcripts.
- Never edit `決めたこと / Decisions` or `課題 / Issues` by hand; the adr and issue
  skills maintain them.

## 3. Status

`kurapika topic status "<topic>" active|paused|done` — use `paused` when the user
parks the work. When the topic seems finished, suggest `/topic-close` (which
digests it into `knowledge/`) instead of just marking it done.
