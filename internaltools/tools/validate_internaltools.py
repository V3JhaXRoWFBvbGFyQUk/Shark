#!/usr/bin/env python3
"""Validate SHARK's internaltools workspace and its registry.

Checks:
  - required directories and registry.json exist and parse
  - every registered skill exists and has usable SKILL.md frontmatter
  - every registered tool exists and has a sibling README
  - every SKILL.md / tool.py on disk is registered

Usage:
    python internaltools/tools/validate_internaltools.py
    python internaltools/tools/validate_internaltools.py --json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

INTERNALTOOLS = Path(__file__).resolve().parents[1]
REGISTRY = INTERNALTOOLS / "registry.json"
SKILL_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _frontmatter(path: Path) -> Dict[str, str]:
    """Return name/description from SKILL.md frontmatter, or an empty dict."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}

    fields: Dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line.strip())
        if match:
            fields[match.group(1).lower()] = match.group(2).strip().strip('"\'')
    return fields


def validate() -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    checked: Dict[str, List[str]] = {"skills": [], "tools": []}

    for directory in ("skills", "tools", "templates"):
        if not (INTERNALTOOLS / directory).is_dir():
            errors.append(f"missing directory: internaltools/{directory}")

    registry: Dict[str, Any] = {}
    if not REGISTRY.is_file():
        errors.append("missing internaltools/registry.json")
    else:
        try:
            registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid registry.json: {exc}")

    registered_skill_paths = set()
    for entry in registry.get("skills", []):
        skill_id = entry.get("id", "")
        relative = entry.get("path", "")
        if not SKILL_ID.match(skill_id):
            errors.append(f"skill id is not kebab-case: {skill_id!r}")
        skill_file = INTERNALTOOLS / relative if relative else None
        if skill_file is None or not skill_file.is_file() or skill_file.name != "SKILL.md":
            errors.append(f"registered skill path is invalid: {relative!r}")
            continue
        registered_skill_paths.add(skill_file.resolve())
        checked["skills"].append(skill_id)
        fields = _frontmatter(skill_file)
        if not fields.get("name"):
            errors.append(f"skill '{skill_id}' has no frontmatter name")
        if not fields.get("description"):
            errors.append(f"skill '{skill_id}' has no description (it will not be advertised)")

    registered_tool_paths = set()
    for entry in registry.get("tools", []):
        name = entry.get("name", "")
        relative = entry.get("path", "")
        tool_file = INTERNALTOOLS / relative if relative else None
        if tool_file is None or not tool_file.is_file():
            errors.append(f"registered tool path is invalid: {relative!r}")
            continue
        registered_tool_paths.add(tool_file.resolve())
        checked["tools"].append(name)
        readme = tool_file.parent / "README.md"
        if not readme.is_file():
            errors.append(f"tool '{name}' has no README at {readme.relative_to(INTERNALTOOLS)}")
        if not entry.get("command"):
            warnings.append(f"tool '{name}' has no command in the registry")

    skills_dir = INTERNALTOOLS / "skills"
    if skills_dir.is_dir():
        for skill_file in skills_dir.rglob("SKILL.md"):
            if skill_file.resolve() not in registered_skill_paths:
                errors.append(f"unregistered skill: {skill_file.relative_to(INTERNALTOOLS)}")

    tools_dir = INTERNALTOOLS / "tools"
    if tools_dir.is_dir():
        for tool_file in tools_dir.glob("*/tool.py"):
            if tool_file.resolve() not in registered_tool_paths:
                errors.append(f"unregistered tool: {tool_file.relative_to(INTERNALTOOLS)}")

    return {
        "ok": not errors,
        "root": str(INTERNALTOOLS),
        "errors": errors,
        "warnings": warnings,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the SHARK internaltools workspace")
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args()

    report = validate()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"[internaltools] root: {report['root']}")
        for warning in report["warnings"]:
            print(f"  WARN: {warning}")
        for error in report["errors"]:
            print(f"  ERROR: {error}")
        if report["ok"]:
            print(
                f"[internaltools] OK - "
                f"{len(report['checked']['skills'])} skill(s), "
                f"{len(report['checked']['tools'])} tool(s) registered"
            )
        else:
            print(f"[internaltools] FAILED - {len(report['errors'])} error(s)")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
