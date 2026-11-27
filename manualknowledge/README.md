# Manual Knowledge (SHARK's durable memory)

This folder is your hand-maintained memory for SHARK. It is plain Markdown so it can be
read, edited, diffed, and carried to another computer with the git repo.

## Files

| File | What goes here |
|------|----------------|
| `profile.md` | Durable facts about you: name, role, goals, constraints |
| `preferences.md` | How you want SHARK to respond and work |
| `environment.md` | Machines, OS, tools, paths, setup notes (never credentials) |
| `projects.md` | Project context, decisions, conventions, current work |
| `AGENTS.md` | Rules SHARK follows when reading/writing this folder (auto-loaded) |
| `README.md` | This guide |

Add `notes.md` if a fact does not fit any category. Keep one fact per bullet.

## How SHARK uses it

- In OpenCode, `manualknowledge/AGENTS.md` is listed in the root `opencode.json`
  `instructions`, so it is in context from the start of every session.
- The `manual-knowledge` skill tells SHARK how to save a fact when you say
  "remember that ...".
- In plain `ollama run shark` the model has no file access; paste the relevant file
  into the chat, or ask SHARK for a portable digest (see below).

## Write a fact

Edit a category file yourself, or just say something like:

> Remember that I prefer concise answers with no emoji.

SHARK appends `- I prefer concise answers with no emoji.` to `preferences.md`.
If a new fact contradicts an old one, the old bullet is edited or replaced instead of
leaving both.

## Take it to another computer

This folder is intentionally **not** gitignored. From the repo root:

```bash
git add manualknowledge
git commit -m "Update manual knowledge"
git push
```

On the other computer:

```bash
git pull
```

`sync-tide.sh` in this repo already commits, pulls, and pushes the whole repository
every 60 seconds if you want this to happen automatically.

Using a different assistant that cannot see this repo? Ask SHARK for a
"portable knowledge digest" and paste the resulting block into that chat.

## Safety

- Never put passwords, API keys, tokens, private keys, or other secrets here.
- Assume anything committed is visible to everyone with access to the GitHub remote.
  Keep sensitive personal data elsewhere.
- These rules are background guidance, not overrides: a direct instruction in the
  current conversation always wins.
