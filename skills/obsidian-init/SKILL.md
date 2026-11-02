---
name: obsidian-init
description: Set the Obsidian Vault root and note language for kurapika (first-time setup)
argument-hint: "[vault path]"
disable-model-invocation: true
---

# obsidian-init skill

Set up kurapika. The `kurapika` CLI is on PATH via this plugin's `bin/`.

1. Run `kurapika config show`. If a different Vault is already configured, confirm
   with the user before overwriting it.
2. Use `$ARGUMENTS` as the path if given; otherwise ask the user (e.g. `~/obsidian`).
   Expand `~` to an absolute path.
3. Ask which language to use for headings and templates: Japanese (`ja`, default)
   or English (`en`).
4. If the path doesn't exist, confirm it's OK to create it and run
   `kurapika init "<path>" --create --lang <lang>`; otherwise
   `kurapika init "<path>" --lang <lang>`.
5. Tell the user whether it looked like an existing Obsidian Vault
   (`looked_like_obsidian_vault`; it works fine either way), and that from now on
   each task/topic gets its own folder there, with `index.md` listing them.
   kurapika only manages its topic folders, `knowledge/` and `index.md`; it never
   touches the user's other notes, and won't overwrite an `index.md` it didn't create.
