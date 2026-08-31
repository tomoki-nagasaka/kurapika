---
name: feature
description: >-
  Starts tracking a new feature or unit of work in the Obsidian Vault before any
  design decision has been made. Triggers on phrases like "let's start working on
  X", "new feature: X", or "I'm about to begin X". Not needed if you're about to
  record an ADR — the adr skill creates the feature folder automatically. It IS
  needed before using the issue or issue-breakdown skills, since issues attach
  to an existing feature and won't create one.
---

# Feature start skill

## Prerequisites

- The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
- Get the Vault root with `kurapika config show`.
  If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
- Use the current working directory's name (`$CLAUDE_PROJECT_DIR` or pwd) as the project name.

## Steps

1. Check `<vault_root>/<project>/TASKS/` for an existing feature this continues
   (`ls "<vault_root>/<project>/TASKS/"`). Reuse its slug if so.
2. For a new feature, come up with an **English kebab-case slug** summarizing it
   (e.g. "add dark mode toggle" → `dark-mode-toggle`), and a human-facing
   `--feature-title`.
3. Run:

   ```bash
   kurapika new-feature \
     --project "<project>" \
     --feature-slug "<feature-slug>" \
     --feature-title "<feature-title>"
   ```

   This creates `TASKS/<feature-slug>/summary.md` and links it from the
   "## In-progress features" section of `summary-todo.md`.
4. Report the feature slug and path to the user in one line.
