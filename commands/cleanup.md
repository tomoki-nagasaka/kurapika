---
description: Run kurapika's mechanical Vault cleanup now
---

Run `kurapika cleanup`. It is the same cleanup the SessionStart hook runs: it
deletes leftover `.bak`/`.tmp` files and empty ADR/ISSUE folders inside topic
folders, and regenerates `index.md`. It only touches what kurapika manages.

Report what was removed (`removed`) in a short list, or say nothing needed
cleaning. If `index` is `conflict`, explain that the Vault already has an
`index.md` not created by kurapika, so it was left untouched.

For things that need judgement (stale topics, long notes, broken links), suggest
the organize skill.
