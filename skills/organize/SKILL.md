---
name: organize
description: >-
  Checks the Obsidian Vault's health (empty feature folders, broken links, gaps or
  duplicates in ADR numbering, features not linked from summary-todo) and reports
  the findings. Use it on explicit requests like "tidy up the Vault" or "check if
  anything's a mess". Does not trigger automatically.
---

# Vault organize / health-check skill

This only reports issues — it never auto-fixes or deletes files.

## Steps

1. The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
   Get the Vault root with `kurapika config show`.
   If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
2. Run the following (add `--project <project>` to check just one project):

   ```bash
   kurapika organize-report --project "<project>"
   ```

3. Summarize the returned JSON for the user in plain language:
   - `empty_features`: feature folders with neither a summary nor any ADRs → suggest
     confirming whether they should be removed
   - `orphan_features`: features not linked from `summary-todo.md` → suggest adding a link
   - `adr_number_issues`: gaps or duplicates in ADR numbering → suggest reviewing and
     fixing manually
   - `broken_links`: broken relative links → suggest checking whether the target was
     moved or deleted
4. If there's nothing to report, say so briefly.
