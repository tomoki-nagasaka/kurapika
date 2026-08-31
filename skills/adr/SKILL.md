---
name: adr
description: >-
  Records a design decision or technology choice as an ADR (Architecture Decision
  Record) in the Obsidian Vault once it has been finalized during development.
  Triggers automatically on phrases like "we decided to do X because Y", "make this
  an ADR", or "we're going with this approach". Do not use it for discussions that
  are still open and haven't reached a conclusion.
---

# ADR recording skill

Once a design decision is finalized, record it as an ADR using the steps below.

## Prerequisites

- The `kurapika` command lives in this plugin's `bin/` and is directly callable via PATH.
- Get the Vault root with `kurapika config show`.
  If it's unconfigured, prompt the user to run `/obsidian-init` and stop without doing anything.
- Use the current working directory's name (`$CLAUDE_PROJECT_DIR` or pwd) as the project name.

## Steps

1. **Determine the feature (the unit of work / functionality)**
   - Check the existing folders under `<vault_root>/<project>/TASKS/`
     (`ls "<vault_root>/<project>/TASKS/"`).
   - If this conversation continues an existing feature, reuse that feature slug.
   - If it's a new topic, come up with an **English kebab-case slug** that summarizes it
     (e.g. "Rails 7 upgrade: remove coffee-rails" → `rails7-upgrade`).
     The slug must be alphanumeric and hyphens only — never put Japanese text in a slug.
   - `--feature-title` is the human-facing title.

2. **Decide the ADR title and slug**
   - `--adr-title` is the human-facing title (e.g. "Remove coffee-rails and cocoon via two staged PRs").
   - `--adr-slug` must be English kebab-case (e.g. `coffee-rails-cocoon-removal`).

3. **Create the ADR**

   ```bash
   kurapika new-adr \
     --project "<project>" \
     --feature-slug "<feature-slug>" \
     --feature-title "<feature-title>" \
     --adr-slug "<adr-slug>" \
     --adr-title "<adr-title>" \
     --status "accepted"
   ```

   This creates `TASKS/<feature-slug>/ADR/ADR-XXXX-<adr-slug>.md`, and also automatically
   appends links to the "## Related ADRs" section of `summary.md` and the
   "## In-progress features" section of `summary-todo.md`.

4. **Fill in the ADR body**
   - Read the `adr_path` returned in the command's JSON output, and fill in the
     `## Context`, `## Decision`, and `## Consequences` sections with what was actually
     discussed (editing the file directly with the Edit tool is fine).
   - Only add an `## Options` section between `## Context` and `## Decision` by hand
     when multiple alternatives were actually compared (it's not in the default template).

5. When done, report the path and a one-line summary of the ADR you created to the user.

## Amending an existing ADR

If the decision changes later, don't create a new ADR — append a dated `> [!note]`
callout to the existing ADR's `## Status` section describing the amendment (edit the
file directly with the Edit tool).
