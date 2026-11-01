---
name: issue
description: >-
  Creates trackable issues inside the current topic in the user's Obsidian Vault,
  either standalone or by breaking an ADR's decision down into tasks. Only on
  explicit request ("issue作成", "issueにして", "このADRをissueに分解して",
  "create an issue", "break this ADR into issues"). Never triggers automatically.
---

# Issue skill

All commands use the `kurapika` CLI and print JSON. If one fails with
`not_configured`, ask the user to run `/obsidian-init` and stop.

## Standalone issue

1. Determine the topic (see the topic skill). Ask before creating a new topic.
2. Run `kurapika issue new --topic "<topic>" --title "<title>"`.
3. Fill in the description and acceptance criteria in the file at `path` (Edit tool).
4. Report its `uri` to the user.

`adr_refs` starts empty; the adr skill appends to it when a decision resolves it.

## Breaking an ADR down

1. Identify the ADR (`kurapika topic show "<topic>"` lists them). Ask if ambiguous.
2. Read its decision section and propose a list of concrete, actionable issues.
   **Confirm the breakdown with the user before creating anything.**
3. For each issue:

   ```bash
   kurapika issue new --topic "<topic>" --title "<title>" --adr-ref "ADR-XXXX-<name>.md"
   ```

4. Fill in each issue's description and acceptance criteria from the ADR.
5. Report the created issues as a list of `uri` links.

## Status changes

Edit the `status` field in the issue's front matter directly (`open`,
`in-progress`, `done`). `kurapika topic show` reads it from there.
