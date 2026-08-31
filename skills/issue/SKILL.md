---
name: issue
description: >-
  Creates a standalone, trackable issue inside the Obsidian Vault to investigate
  an open question before any decision/ADR exists. Use it on explicit requests
  like "create an issue", "issue作成", or "let's track this as an issue". Not
  for breaking an existing ADR's decision into issues — use the issue-breakdown
  skill for that. Does not trigger automatically.
---

# Issue creation skill

## Prerequisites

- The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
- Get the Vault root with `kurapika config show`.
  If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
- The target feature must already exist (created by the `feature` or `adr` skill).
  If `TASKS/<feature>/` doesn't exist yet, tell the user and stop — don't create it here.

## Steps

1. Confirm the target feature already exists (see Prerequisites).
2. Decide an **English kebab-case** `--issue-slug` and a human-facing
   `--issue-title` for the open question to investigate, then run:

   ```bash
   kurapika new-issue \
     --project "<project>" \
     --feature-slug "<feature-slug>" \
     --issue-slug "<issue-slug>" \
     --issue-title "<issue-title>" \
     --status "open"
   ```

   This creates `TASKS/<feature-slug>/ISSUE/ISSUE-XXXX-<issue-slug>.md`
   (numbered per-feature in 4 digits, same scheme as ADRs) with an empty
   `adr_refs` list.
3. Fill in `## Description` and `## Acceptance Criteria` based on the open
   question (editing directly with the Edit tool is fine).
4. Report the created issue path to the user, and mention: whenever a decision
   is reached for this issue, running the `adr` skill and mentioning this issue
   will append the new ADR to its `adr_refs` list. This can happen more than
   once over the issue's lifetime — a single issue may accumulate several ADRs
   as it's investigated further.
