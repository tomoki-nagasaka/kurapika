---
name: recall
description: >-
  Answers "what was that again?" questions from the user's Obsidian Vault: what a
  topic is about, how far it got, what was done and decided, with links. Use it on
  phrases like "あれなんだっけ", "〇〇ってどうなってたっけ", "前に〇〇どうしたっけ",
  "〇〇について調べたことある？", "what did we decide about X?", "where are we on X?".
---

# Recall skill

All commands use the `kurapika` CLI and print JSON. If one fails with
`not_configured`, ask the user to run `/obsidian-init` and stop.

## Steps

1. Find the topic.
   - If the question clearly names an active topic (the SessionStart hook listed
     them), go straight to step 2.
   - Otherwise run `kurapika search "<keywords>"` (space-separated terms; try 1-2
     alternative wordings if nothing comes back). It searches topics and
     `knowledge/` (closed topics) and returns paths, snippets and `uri`s.
   - If several topics match, first show the candidates (title, one line, link)
     and let the user pick.
2. For a topic: `kurapika topic show "<topic>"`. For a knowledge file: read it.
3. Answer in this shape (in the user's language), then answer the actual question
   using the details:

   ```
   📁 <title>（<status_label> / 最終更新 <updated>）
   一言で：<oneline>
   現状：<now>
   経緯：
     - <history_recent, newest first, up to 5>
   🔗 summary: <uri>
   🔗 <ADR / ISSUE title>: <uri>   ← only the ones relevant to the question
   ```

4. Read ADR/ISSUE files only when the question needs their content (e.g. *why*
   something was decided). Quote the reasoning briefly and link the file.

Don't dump whole files into the answer; the links are there for the full text.
