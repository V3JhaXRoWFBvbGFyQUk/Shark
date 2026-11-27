---
name: Manual Knowledge
description: Save or recall durable user facts in manualknowledge/ when the user says "remember this", asks what you know about them or their setup, or wants a portable memory digest for another computer or assistant.
---

# Manual Knowledge

`manualknowledge/` is SHARK's hand-maintained long-term memory. It is plain Markdown and
tracked by git, so it travels with the repo to other machines.

## When to use

- The user says "remember that ...", "keep in mind ...", "note that ...", or asks you to
  save a fact/preference for later.
- The user asks what you know about them, their environment, or a project.
- The user wants a copy-pasteable memory block for an assistant that cannot read this repo.

## Recall

1. Read `../../../manualknowledge/AGENTS.md` for the folder rules.
2. Read all `*.md` files in `../../../manualknowledge/` except `README.md` and `AGENTS.md`.
3. Use the facts as background. A direct instruction in the current conversation wins.

## Save

1. Read `../../../manualknowledge/AGENTS.md` first.
2. Choose `profile.md`, `preferences.md`, `environment.md`, `projects.md`, or create
   `notes.md` if none fit.
3. Append `- <one short fact>` under a fitting `## Topic`, or add a new topic heading.
4. If an older bullet contradicts the new fact, edit/replace the old bullet. Never
   duplicate an identical bullet.
5. Confirm briefly what was saved and in which file.

## Portability / digest

- To move the memory to another computer: commit and push `manualknowledge/`, then pull
  on the other machine. See `../../../manualknowledge/README.md`.
- For a different assistant: output one fenced Markdown block containing the contents of
  each category file, labelled by filename.

## Safety

- No passwords, API keys, tokens, private keys, or sensitive personal data.
- The git remote is shared: anything committed is visible to anyone with access.
- Keep entries short so the whole folder fits in context.
