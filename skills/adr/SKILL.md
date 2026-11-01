---
name: adr
description: >-
  Records a finalized design decision or technology choice as an ADR inside the
  current topic in the user's Obsidian Vault. Use it when a conclusion has been
  reached ("〜に決めた", "〜でいこう", "ADRにして", "we decided to X because Y",
  "make this an ADR"). Not for open discussions or tentative ideas (those go to
  the topic skill's `direction`).
---

# ADR skill

An ADR is the formal record of *why* something was decided. It's the most valuable
part of a topic, so keep the reasoning, not just the outcome.

All commands use the `kurapika` CLI and print JSON. If one fails with
`not_configured`, ask the user to run `/obsidian-init` and stop.

## Steps

1. Determine the topic (see the topic skill). If there is none yet, propose one and
   ask before creating it.
2. Propose the ADR title and a 2-3 line summary of the decision, and **ask before
   creating it**.
3. Create it:

   ```bash
   kurapika adr new --topic "<topic>" --title "<title>" [--status accepted]
   ```

   This creates `<topic>/ADR/ADR-XXXX-<title>.md`, adds a link under
   `決めたこと / Decisions` in summary.md, and logs it in the history.
4. Fill in the body of the file at `path` (Edit tool): background/context, the
   decision, and consequences (good points and trade-offs). Add an options section
   only if alternatives were actually compared.
5. If the decision came from an existing issue, add a link to that issue in the ADR
   and append this ADR's filename to the issue's `adr_refs` front matter (keep
   existing entries; update its `status` if resolved).
6. If the topic's `direction` described this decision as tentative, update it with
   `kurapika note "<topic>" direction`.
7. Report the created file to the user as its `uri` (an `obsidian://` link).

## Amending an ADR

Don't create a new ADR for a change of mind on the same point. Append a dated
`> [!note]` callout under its status section describing the amendment.
