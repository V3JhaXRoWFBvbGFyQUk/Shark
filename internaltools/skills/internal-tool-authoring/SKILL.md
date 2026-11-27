---
name: SHARK Internal Tool Authoring
description: Create, register, validate, and reload SHARK's own skills and tools in internaltools/ when a repeatable capability is needed; use instead of rebuilding the same capability each session.
---

# SHARK Internal Tool Authoring

Use this skill when you need a capability you will reuse across SHARK sessions.
`internaltools/` is your own workspace: skills hold reusable procedure, tools hold
reusable execution. Anything you add here becomes part of your future self.

## 1. Decide what to build

1. Read `../../registry.json` (relative to this file) and the sibling `skills/` and
   `tools/` directories. Reuse an existing entry if it fits.
2. **Skill** — repeatable knowledge: a workflow, checklist, playbook, or convention.
3. **Tool** — repeatable action: parsing, crawling, decoding, indexing, validation,
   reporting, or another executable utility.
4. If neither is genuinely reusable, just do the task; do not create clutter.

## 2. Author a skill

- Directory: `internaltools/skills/<kebab-case-id>/SKILL.md`.
- Frontmatter is mandatory for discovery:

  ```markdown
  ---
  name: Human Readable Name
  description: One precise sentence describing exactly when to use this skill.
  ---
  ```

- The file path sets the skill ID; `name` is only a display label. Keep them aligned.
- `description` is what gets advertised to you at each step. Without it the skill is
  invisible to model invocation.
- Keep scripts/references next to `SKILL.md` in `scripts/` or `references/`. All paths
  inside the skill are relative to the skill's own directory.
- Do not nest another `SKILL.md` inside a skill directory; OpenCode stops at the first.

## 3. Author a tool

- Directory: `internaltools/tools/<name>/` containing:
  - `tool.py` with a `--help` CLI, clear argument parsing, and `--json` when output is
    meant to be consumed programmatically
  - `README.md` with purpose, usage examples, inputs/outputs, dependencies, and safety
    notes
- Copy `templates/tool.py.tmpl` and `templates/tool.README.md.tmpl` from
  `internaltools/templates/` as starting points.
- Small single-file tools may live directly at `internaltools/tools/<name>.py`, but a
  directory with a README is preferred.
- Tools must be safe to re-run, avoid destructive defaults, and never embed secrets.

## 4. Register

Add one entry to `registry.json` under `skills` or `tools`:

```json
{
  "id": "my-skill",
  "path": "skills/my-skill/SKILL.md",
  "purpose": "Short why-it-exists note",
  "created": "YYYY-MM-DD"
}
```

Tools use `name`, `path`, `command`, `purpose`, and `created`.

## 5. Validate and activate

```bash
python internaltools/tools/validate_internaltools.py
```

Fix every reported error. Then run `/reload` so OpenCode re-discovers skills and
instructions. Skills added to a registered source are advertised only when they have
a `description`; confirm the new skill appears before relying on it.

## 6. Safety contract

- Authorized, legal, ethical security work only.
- No unauthorized scanning, exploitation, credential use, or data exfiltration.
- Never persist secrets or sensitive collected data in this workspace.
- Keep the registry accurate; unregistered additions are unfinished work.
- When you change an existing skill or tool, update its registry entry and README too.
