---
name: issue-breakdown
description: >-
  Breaks an ADR's decision down into one or more concrete, trackable issues
  inside the Obsidian Vault. Use it on explicit requests like "break this ADR
  into issues", "turn this decision into tasks", or "issueに分解して". Does not
  trigger automatically.
---

# Issue breakdown skill

## Prerequisites

- The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
- Get the Vault root with `kurapika config show`.
  If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
- The target feature must already exist (created by the `feature` or `adr` skill).
  If `TASKS/<feature>/` doesn't exist yet, tell the user and stop — don't create it here.

## Steps

1. Identify the ADR the user is referring to. If it's ambiguous, list
   `TASKS/<feature>/ADR/` and ask which one.
2. Read that ADR file and propose a breakdown of its `## Decision` section into
   one or more concrete, actionable issues. Confirm the breakdown with the user
   before creating anything.
3. For each issue, decide an **English kebab-case** `--issue-slug` and a
   human-facing `--issue-title`, then run:

   ```bash
   kurapika new-issue \
     --project "<project>" \
     --feature-slug "<feature-slug>" \
     --issue-slug "<issue-slug>" \
     --issue-title "<issue-title>" \
     --adr-ref "ADR-XXXX-slug.md" \
     --status "open"
   ```

   This creates `TASKS/<feature-slug>/ISSUE/ISSUE-XXXX-<issue-slug>.md`
   (numbered per-feature in 4 digits, same scheme as ADRs), recording the ADR
   as the first entry in the issue's `adr_refs` list.
4. Fill in `## Description` and `## Acceptance Criteria` for each created issue
   based on the ADR content (editing directly with the Edit tool is fine).
5. Report the created issue paths to the user.
