---
name: organize
description: >-
  Tidies up the user's Obsidian Vault where judgement is needed: stale topics,
  overgrown notes, broken links, stray folders. Use it on explicit requests
  ("Vault整理して", "散らかってないか見て", "tidy up the Vault") or when the user
  agrees to the SessionStart hook's tidy-up suggestion. Never changes anything
  without confirmation.
---

# Organize skill

Mechanical cleanup (leftover files, empty folders, regenerating `index.md`)
already runs automatically in the SessionStart hook.
This skill handles what needs a human decision.

All commands use the `kurapika` CLI and print JSON. If one fails with
`not_configured`, ask the user to run `/obsidian-init` and stop.

## Steps

1. Run `kurapika organize-report` (this also resets the "time to tidy up" timer).
2. Turn the report into a short numbered proposal list, one action per item:

   | Report key                | Proposal                                                                                             |
   | ------------------------- | ---------------------------------------------------------------------------------------------------- |
   | `stale_topics`            | Close it (`/topic-close` flow), pause it (`kurapika topic status <t> paused`), or keep going          |
   | `long_sections`           | Condense older `research` / `history` entries into a few lines (show the rewrite before applying)    |
   | `broken_links`            | Fix the link target or remove the link                                                                 |
   | `folders_without_summary` | Not managed by kurapika (e.g. a 0.x project folder or the user's own folder): just mention; delete only if the user asks |
   | `numbering_issues`        | Mention only; renumbering breaks existing links                                                      |
   | `index: conflict`         | The user's own `index.md` exists; kurapika won't overwrite it. Ask whether to rename theirs           |

3. **Ask which items to apply.** Apply only those, one at a time, and report each.
   For condensing, rewrite the section via the Edit tool on `summary.md`, keeping
   dates of key events.
4. If nothing was reported, say the Vault is tidy in one line.
