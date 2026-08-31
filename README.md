<p align="center">
  <img src="assets/banner.svg" alt="Claude Note" width="100%">
</p>

# kurapika

A Claude Code plugin that automatically accumulates ADRs, feature summaries, and
project-wide TODOs in an Obsidian Vault, per development project.

## Requirements

- **Python 3.9+** (tested on 3.9.6). Standard library only
  (`json`, `os`, `pathlib`, `re`, `fcntl`, `argparse`, `datetime`, `contextlib`, `time`).
  No extra install needed.
- **macOS or Linux** (the lock mechanism uses `fcntl`, so Windows is not supported)
- **Claude Code CLI** (tested on 2.1.251). Check with `claude --version`.
  You need a version that supports plugins (hooks / commands / skills).
- **Obsidian itself is not required.** The Vault is just a plain Markdown folder, so
  install Obsidian only if you also want to browse it and view the graph.

## Setup

### 1. Clone it

```bash
git clone <this repo's URL> kurapika
```

### 2. Register it as a marketplace and install it

This repo ships its own `.claude-plugin/marketplace.json`, so you can register the
cloned directory as a self-hosted, single-plugin marketplace and install from it —
no submission to Anthropic's official marketplace needed.

```bash
claude plugin marketplace add /path/to/kurapika
claude plugin install kurapika@kurapika-marketplace --scope user
```

`--scope user` makes kurapika available in every `claude` session on this machine,
no matter which directory you start it from — that's what makes the SessionStart
hook and skills apply automatically everywhere. Restart any running `claude`
sessions for the install to take effect.

**Updating after you pull or edit the source**: the installed copy is a cached
snapshot, not a live link to your clone, and it's only refreshed when the plugin's
version number changes. After bumping `version` in `.claude-plugin/plugin.json`
(and the matching entry in `marketplace.json`), run:

```bash
claude plugin marketplace update kurapika-marketplace
claude plugin update kurapika@kurapika-marketplace
```

then restart `claude` to pick up the change.

**Alternative for quick local testing**: to try changes without touching your
installed version or bumping the version number, load the working directory
directly for a single session instead:

```bash
claude --plugin-dir /path/to/kurapika
```

### 3. Set the Vault root

Run this once, the first time you start a session.

```
/obsidian-init
```

You'll be asked for the Vault root path (the parent folder to use as your Obsidian
Vault). It can be an existing Obsidian Vault or a brand-new folder. This setting is
independent per user and per machine (see "Configuration file" below).

## Commands

Slash commands you invoke explicitly.

| Command                    | Description                                                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `/obsidian-init [path]`    | First-time setup command that sets the Obsidian Vault root path for kurapika. Prompts interactively if `path` is omitted |
| `/obsidian-reset`          | Clears the Vault root path setting and returns to an unconfigured state (never deletes notes inside the Vault)           |
| `/project-reset [project]` | Moves a project's Vault data into `.trash/` (a recoverable move, not a permanent delete)                                 |

## Hooks

Run automatically in response to session events.

| Event          | When it runs                                             | What it does                                                                                                                                                                                                                                                                                                               |
| -------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SessionStart` | On `claude` startup (startup / resume / clear / compact) | Looks at the `CLAUDE_PROJECT_DIR` folder name and creates `<project>/summary-todo.md` and `<project>/TASKS/` in the Vault if they don't exist yet. If the Vault isn't configured, or its path can't be found, it just prints a one-line warning and does nothing (a fail-safe against creating folders in the wrong place) |

## Skills

Used automatically by Claude during conversation (or on explicit request).

| Skill      | Trigger                                                                                                    | What it does                                                                                                                                                                                                                 |
| ---------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `adr`      | A design decision or technology choice has been finalized, or on explicit requests like "make this an ADR" | Creates `TASKS/<feature>/ADR/ADR-XXXX-<slug>.md` (numbered per-feature in 4 digits). Also auto-appends cross-links to the "related ADRs" section of `summary.md` and the "in-progress features" section of `summary-todo.md` |
| `summary`  | A non-ADR progress update, a milestone, or a TODO change is detected                                       | Updates the relevant section of `summary.md` (per feature) or `summary-todo.md` (project-wide) (backs up to `.bak` before writing)                                                                                           |
| `search`   | Phrases like "what did we decide about X again?" or "find past notes about X"                              | Scores Vault Markdown files by filename / heading / body match and surfaces relevant files (grep-based, no dependencies)                                                                                                     |
| `organize` | Explicit requests like "tidy up the Vault" or "check if anything's a mess" (never triggers automatically)  | Detects and reports empty feature folders, features not linked from `summary-todo.md`, gaps/duplicates in ADR numbering, and broken relative links (never auto-fixes anything)                                               |

## Vault layout

```
<vault-root>/
  <project-name>/
    summary-todo.md
    TASKS/
      <feature-slug>/
        summary.md
        ADR/
          ADR-0001-<slug>.md
```

Directory and file names are alphanumeric kebab-case, and the generated templates
(headings, labels) are in English.

## Internal CLI (`kurapika`)

All of the commands/hooks/skills above are just thin wrappers around `bin/kurapika`
(callable via PATH). Feel free to run it directly when debugging.

| Subcommand                                                                                                     | Effect                                                                                              |
| -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `kurapika init <path> [--create]`                                                                              | Sets the Vault root path. Use `--create` to create the path if it doesn't exist                     |
| `kurapika config show`                                                                                         | Shows the current setting (Vault root path)                                                         |
| `kurapika config clear [--confirm]`                                                                            | Clears the setting. Without `--confirm`, only shows what would be cleared                           |
| `kurapika reset-project --project P [--confirm]`                                                               | Moves a project into `.trash/`. Without `--confirm`, only shows the target path and file count      |
| `kurapika hook session-start`                                                                                  | The actual work behind the SessionStart hook (reads `CLAUDE_PROJECT_DIR` and scaffolds the project) |
| `kurapika new-adr --project P --feature-slug F --feature-title T --adr-slug S --adr-title A [--status STATUS]` | Creates a new ADR and auto-links it from the summary/TODO                                           |
| `kurapika update-doc --path PATH --heading "## Heading"` (body read from stdin)                                | Upserts the body of the given section                                                               |
| `kurapika search QUERY [--project P] [--limit N]`                                                              | Searches the Vault by keyword                                                                       |
| `kurapika organize-report [--project P]`                                                                       | Prints the health-check report as JSON                                                              |

## Configuration file

The Vault root path is stored per user in `~/.config/kurapika/config.json`. Since the
clone location and Vault location differ from person to person, this file is not
tracked in git — each user creates their own by running `/obsidian-init`.

## Uninstalling

Fully removing kurapika takes two commands, since installing it registered two
separate things (the marketplace and the plugin installed from it):

```bash
claude plugin uninstall kurapika@kurapika-marketplace
claude plugin marketplace remove kurapika-marketplace
```

Notes:

- `plugin uninstall` alone removes it from `claude plugin list` and disables the
  hook/commands/skills, but the cached copy under
  `~/.claude/plugins/cache/kurapika-marketplace/` is left behind (marked as
  orphaned rather than deleted immediately). Also running `marketplace remove`
  cleans up the marketplace registration itself.
- Neither command touches your Vault. To also clear the Vault root setting, run
  `/obsidian-reset` (or delete `~/.config/kurapika/config.json` directly) before
  uninstalling. Your notes inside the Vault are never deleted by any of this —
  if you want those gone too, remove the Vault directory yourself.
