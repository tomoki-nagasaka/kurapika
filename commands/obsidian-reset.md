---
description: Clear the Vault root path setting and return to an unconfigured state
---

Delete the Vault root path setting (`~/.config/kurapika/config.json`).
**This never deletes any notes inside the Vault** — it only clears the configuration.

1. Run `kurapika config show` to check the current setting. If it's unconfigured, say so and stop.
2. Show the user the currently configured Vault root path and confirm they really want to
   clear it. Make clear that no files in the Vault will be deleted.
3. Once confirmed, run `kurapika config clear --confirm`.
4. When done, let the user know that Vault integration is now disabled until they run
   `/obsidian-init` again.
