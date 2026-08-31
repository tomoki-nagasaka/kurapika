---
description: Set the Obsidian Vault root path for kurapika (first-time setup)
---

Set the Obsidian Vault root path (the parent folder under which project folders will live).
The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.

1. Run `kurapika config show` to check the current setting.
   If a different Vault path is already configured, confirm with the user before overwriting it.
2. If argument `$ARGUMENTS` is given, use it as the path. Otherwise ask the user
   (suggested example: `~/obsidian`).
3. Expand `~` and resolve the path to an absolute path.
4. Check whether the path exists.
   - If it doesn't exist: confirm with the user that it's OK to create it, then run
     `kurapika init "<path>" --create`.
   - If it exists: run `kurapika init "<path>"`.
5. Look at `looked_like_obsidian_vault` in the command's JSON output and tell the user
   whether it looks like an existing Obsidian Vault (reassure them that it works fine
   even without `.obsidian/`, so they don't need to worry if it's missing).
6. Once it succeeds, show the result again with `kurapika config show` and let the user
   know that from now on, project folders will be created automatically in the Vault
   based on the directory name where `claude` is run.
