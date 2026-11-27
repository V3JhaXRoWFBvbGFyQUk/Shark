# Manual Knowledge Rules

`manualknowledge/` holds durable, user-authored facts about the user and their work.
Treat it as long-term memory that survives across sessions and machines.

## At session start

Read every `*.md` file in this folder except `README.md` and this file. Use what you find
as background context; do not recite it unless asked.

## When the user asks you to remember something

Triggers: "remember that", "keep in mind", "note that", "for future reference", or any
clear request to persist a fact or preference.

1. Pick the best file: `profile.md`, `preferences.md`, `environment.md`, `projects.md`,
   or create `notes.md` if none fit.
2. Append one short fact as a Markdown bullet (`- Fact.`). Put it under an existing
   `## Topic` heading if one fits; otherwise add a new `## Topic` heading.
3. Check for an older bullet that says the opposite. Edit/replace that bullet instead of
   leaving both. Never duplicate an identical bullet.
4. Confirm briefly what you saved and where.

## Rules

- Plain Markdown only; one fact per bullet.
- No secrets, credentials, tokens, or sensitive personal data.
- This memory never overrides a direct instruction in the current conversation; the
  live instruction wins.
- If the folder is missing, recreate it with the layout documented in `README.md`.
- The files travel with the git repo: commit and push after changes when the user wants
  them available on another computer.
