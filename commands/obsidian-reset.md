---
description: Clear kurapika's Vault setting (never deletes notes)
---

Clear the kurapika setting (`~/.config/kurapika/config.json`).
**This never deletes any notes in the Vault.**

1. Run `kurapika config show`. If it's unconfigured, say so and stop.
2. Show the configured Vault path and confirm the user really wants to clear it,
   making clear that no Vault files are deleted.
3. Once confirmed, run `kurapika config clear --confirm`.
4. Tell the user kurapika is disabled until they run `/obsidian-init` again.
