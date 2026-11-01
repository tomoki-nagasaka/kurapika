---
description: Switch to a topic, or create it if it doesn't exist
argument-hint: "[topic name]"
---

Switch the current work to the topic `$ARGUMENTS` (follow the topic skill).

1. If `$ARGUMENTS` is empty, run `kurapika topic list` and ask which topic to use
   (or whether to start a new one).
2. Otherwise run `kurapika topic show "$ARGUMENTS"`.
   - Found: from now on, record to this topic. Briefly show its one-line summary,
     current status and the latest history entries, with the summary `uri`.
   - `topic_ambiguous`: show the `candidates` and ask which one.
   - `topic_not_found`: confirm, then `kurapika topic new --title "$ARGUMENTS"`, and
     ask the user for (or propose) the one-line summary to record as `oneline`.
