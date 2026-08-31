---
name: search
description: >-
  Searches past ADRs, summaries, and TODOs in the Obsidian Vault by keyword. Use it
  on phrases like "what did we decide about X again?" or "find past notes about X".
---

# Vault search skill

## Steps

1. The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
   Get the Vault root with `kurapika config show`.
   If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
2. Decide the search query (Japanese is fine as-is). If it's vague, pull out 1-3 key
   terms from the user's message.
3. Run the following (add `--project <project>` to scope to the current project;
   omit it to search across all projects):

   ```bash
   kurapika search "<query>" --project "<project>" --limit 10
   ```

4. Open a few of the top-scoring files with Read and summarize the relevant parts for
   the user. If there are no hits, feel free to retry once or twice with a different query.
