---
name: topic-close
description: >-
  Closes a finished topic in the user's Obsidian Vault: digests it into
  knowledge/ and deletes its folder. Use it on "/topic-close", "このトピック閉じて",
  "〇〇は終わったのでまとめて", "close this topic", or when the user agrees to close
  a stale or finished topic suggested by the topic or organize skill. Always
  confirms before deleting.
argument-hint: "[topic name]"
---

# topic-close skill

Close the topic `$ARGUMENTS` (the current topic if empty). Its folder is deleted,
so the digest must keep everything worth reusing.

All commands use the `kurapika` CLI and print JSON. If one fails with
`not_configured`, ask the user to run `/obsidian-init` and stop.

1. Run `kurapika topic show "<topic>"`. It accepts a partial name; from here on
   use the exact `name` it returns. Read `summary.md` (`path`) plus every file
   listed in `adrs` / `issues` (they live in `ADR/` and `ISSUE/` next to it).
2. Draft the digest in the configured language (check `kurapika config show`):

   ```
   ## 結論 / Conclusion          how it ended up, in a few lines
   ## 決めたこと / Decisions       each ADR: the decision and *why*, 1-2 lines each
   ## 学び・ハマりどころ / Lessons  pitfalls and insights worth remembering
   ## 再利用できるもの / Reusable   commands, config snippets, reference links
   ```

   Issues only need their outcome. Don't include the title or front matter
   (they're added automatically).
3. Run `kurapika topic close "<name>"` (preview) and show the user the digest
   together with `would_delete` and `knowledge_path`. **Ask for confirmation.**
4. Once confirmed, pipe the digest in:
   `printf '%s\n' "<digest>" | kurapika topic close "<name>" --confirm`
5. Report the knowledge file's `uri`.
