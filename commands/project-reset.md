---
description: Move a project's Vault data into the trash (.trash)
---

Move a specific project folder (`<vault_root>/<project>/`) out of the way.
**This is not a permanent delete — it only moves the folder into the Vault's `.trash/`**
(so an accidental reset can still be recovered).

1. If argument `$ARGUMENTS` is given, use it as the project name. Otherwise suggest the
   current working directory's name as a candidate and confirm with the user.
2. First run `kurapika reset-project --project "<project>"` without the confirm flag to
   check the target path and how many files it contains (nothing changes at this point).
3. Show the user the target path and file count, and confirm they really want to move it.
   Make clear that it's not permanently deleted — it's moved to `.trash/` and can be
   restored manually if needed.
4. Once confirmed, run `kurapika reset-project --project "<project>" --confirm`.
5. When done, report the destination path (`.trash/<project>-<timestamp>/`) in one line.
