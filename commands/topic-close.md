---
description: Close a topic - digest it into knowledge/ and delete its folder
argument-hint: "[topic name]"
---

Close the topic `$ARGUMENTS` (the current topic if empty). Its folder is deleted,
so the digest must keep everything worth reusing.

1. Run `kurapika topic show "<topic>"` and read `summary.md` plus every ADR and
   ISSUE file it lists.
2. Draft the digest in the configured language (check `kurapika config show`):

   ```
   ## 結論 / Conclusion          how it ended up, in a few lines
   ## 決めたこと / Decisions       each ADR: the decision and *why*, 1-2 lines each
   ## 学び・ハマりどころ / Lessons  pitfalls and insights worth remembering
   ## 再利用できるもの / Reusable   commands, config snippets, reference links
   ```

   Issues only need their outcome. Don't include the title or front matter
   (they're added automatically).
3. Run `kurapika topic close "<topic>"` (preview) and show the user the digest
   together with `would_delete` and `knowledge_path`. **Ask for confirmation.**
4. Once confirmed, pipe the digest in:
   `printf '%s\n' "<digest>" | kurapika topic close "<topic>" --confirm`
5. Report the knowledge file's `uri`.
