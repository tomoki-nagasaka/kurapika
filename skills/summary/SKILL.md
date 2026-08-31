---
name: summary
description: >-
  Reflects progress updates that don't involve an ADR — status changes on a feature,
  or changes to the project's overall TODOs — into the Obsidian Vault's summary.md /
  summary-todo.md. Triggers automatically on phrases like "here's how far we got",
  "this is done", or "next we'll do X". For recording the decision itself, use the
  adr skill instead.
---

# Summary/TODO update skill

## Prerequisites

- The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
- Get the Vault root with `kurapika config show`.
  If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
- Use the current working directory's name as the project name.

## Steps

1. Decide what to update.
   - If a specific feature's status or next steps changed →
     `<vault_root>/<project>/TASKS/<feature-slug>/summary.md`
   - If the project's overall TODOs or in-progress feature list changed →
     `<vault_root>/<project>/summary-todo.md`
2. Decide which section heading to update (e.g. `## Overview`, `## Next steps`,
   `## Recent updates`) and put together the full new body for that section.
3. Update it by passing the body on stdin, as below (the existing content is backed up
   to `.bak` first):

   ```bash
   kurapika update-doc \
     --path "<project>/TASKS/<feature-slug>/summary.md" \
     --heading "## Next steps" <<'EOF'
   - Next step content
   EOF
   ```

   Give `--path` as a path relative to `<vault_root>`
   (for `summary-todo.md`, that's `"<project>/summary-todo.md"`).
4. After updating, report what changed to the user in one line.
