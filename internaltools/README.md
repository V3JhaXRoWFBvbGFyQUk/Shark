# SHARK Internal Tools

This directory is SHARK's **self-extension workspace**. When SHARK needs a
capability it will reuse, it authors it here and registers it in `registry.json`,
so future sessions can discover and reuse it instead of rebuilding it.

## Layout

```
internaltools/
├── AGENTS.md                          # Instructions loaded into SHARK's context
├── README.md                          # This file (human-facing overview)
├── registry.json                      # Catalog of authored skills and tools
├── skills/                            # SHARK-authored OpenCode skills
│   └── internal-tool-authoring/
│       └── SKILL.md                   # Seed skill: the authoring workflow
├── tools/                             # SHARK-authored executable tools
│   ├── validate_internaltools.py      # Seed tool: workspace validator
│   └── README.md                      # Tool contract
└── templates/                         # Starting points for new skills/tools
    ├── SKILL.md.tmpl
    ├── tool.py.tmpl
    └── tool.README.md.tmpl
```

## How SHARK knows about it

- `AGENTS.md` is loaded as project instructions (registered in the root `opencode.json`),
  so the convention is in context from the first message.
- `internaltools/skills` is registered as an OpenCode skills source in the root
  `opencode.json`, so skills with a `description` are advertised to the model and
  can be loaded with the `skill` tool.
- `registry.json` is the single source of truth for what exists.

The model's system prompt in `model/Modelfile` also mentions this workspace so a
plain Ollama session knows to look here.

## Validate

```bash
python internaltools/tools/validate_internaltools.py
python internaltools/tools/validate_internaltools.py --json
```

## Add something

Read `internaltools/skills/internal-tool-authoring/SKILL.md`; it is the checklist
SHARK uses to create, register, validate, and reload new skills and tools.
