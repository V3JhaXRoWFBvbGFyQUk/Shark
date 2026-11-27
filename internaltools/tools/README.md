# Internal Tools Contract

Tools here are executable utilities SHARK authors for its own reuse. Every tool
should follow this contract so SHARK can call it without guessing.

## Required

- A `--help` flag that explains purpose and arguments.
- Documented inputs and outputs in a sibling `README.md`.
- An entry in `internaltools/registry.json` with the exact command to run.
- Safe defaults: no destructive action without an explicit flag; no hidden network
  calls; no embedded credentials.

## Recommended

- `--json` output for machine-readable results.
- Deterministic behavior and exit codes: `0` success, non-zero failure.
- Stdlib-only unless a dependency is documented in the tool's README.

## Current tools

| Tool | Command | Purpose |
|------|---------|---------|
| `validate_internaltools` | `python internaltools/tools/validate_internaltools.py` | Check workspace structure, skill frontmatter, and registry consistency |

Validate the workspace with `python internaltools/tools/validate_internaltools.py`.
