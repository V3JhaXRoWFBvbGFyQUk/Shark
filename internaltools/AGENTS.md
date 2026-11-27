# SHARK Internal Tools

`internaltools/` is SHARK's self-extension workspace: the place where you (SHARK)
author and reuse your **own** skills and tools. Treat it as part of your own
capabilities, not as user data or a scratch directory.

## Decision rule

- Use a **skill** for repeatable *knowledge or procedure*: a workflow, checklist,
  playbook, convention, or domain guide you would otherwise re-derive each session.
- Use a **tool** for repeatable *execution*: a script or CLI that performs an action
  (parsing, crawling, decoding, indexing, validating, transforming, reporting).
- Always check `internaltools/registry.json` first. Reuse what exists; only create
  something new when nothing registered fits the need.

## Creating a skill

1. Choose a lowercase kebab-case id (e.g. `log-triage`).
2. Create `internaltools/skills/<id>/SKILL.md` with frontmatter:

   ```markdown
   ---
   name: Human Readable Name
   description: One precise sentence saying when to use this skill.
   ---
   ```

   `description` is required. Without it OpenCode will not advertise the skill to you.
3. Keep supporting files beside `SKILL.md` in `scripts/` or `references/`. Paths
   inside a skill are relative to the directory containing `SKILL.md`.
4. Add an entry under `skills` in `internaltools/registry.json`.
5. Run `/reload` after saving so OpenCode picks up the new skill, then tell the user
   what you added.

## Creating a tool

1. Create `internaltools/tools/<name>/` with:
   - `tool.py` (or another executable) exposing `--help` and, where useful, `--json`
   - `README.md` covering purpose, usage, inputs/outputs, and safety notes
2. Add an entry under `tools` in `internaltools/registry.json` with its command.
3. Validate the workspace: `python internaltools/tools/validate_internaltools.py`.
4. Only use the tool after validation passes.

Templates live in `internaltools/templates/`; copy them rather than starting blank.

## Rules for everything you author here

- Authorized, legal, ethical security work only. No unauthorized scanning,
  exploitation, credential use, or targeting of systems you do not own or have
  written permission to test.
- Never store secrets, credentials, or collected sensitive data in this folder.
- Tools should be deterministic where possible, safe to re-run, and document what
  they read or write.
- Keep the registry in sync. An unregistered skill or tool is considered unfinished.
- Prefer the seed skill `internal-tool-authoring` for the full workflow and checklist.
