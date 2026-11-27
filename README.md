# SHARK AI

SHARK is a specialized cybersecurity AI designed for advanced security research,
vulnerability analysis, authorized penetration testing, red-team simulations,
exploit research in isolated labs, reverse engineering, CTFs, and defensive security.

## Identity

- Project identity: SHARK AI
- Model name: SHARK
- Ollama model: shark
- OpenCode identifier: ollama/shark:latest
- Default model configuration: SHARK
- Custom system prompt: SHARK Cybersecurity Assistant

## Quick Start

### Using Ollama

```bash
ollama create shark -f model/Modelfile
ollama run shark
```

### Using OpenCode (Recommended)

SHARK now supports OpenCode, allowing you to launch a fully-featured AI assistant
without needing `ollama launch`.

```bash
.\scripts\launch_shark.bat
```

or

```bash
python scripts\shark_launch.py
```

## Features

- **Extremely Smart**: Upgraded to Qwen2.5 7B parameter model for enhanced reasoning
- **Web Crawling**: Built-in web crawler for security research and threat intelligence
- **OpenCode Support**: Native OpenCode integration with custom launch command
- **Security Focused**: Specialized in cybersecurity tasks including:
  - Vulnerability assessment and exploit analysis
  - Threat intelligence and attack vectors
  - Reverse engineering and malware analysis
  - Cryptography and encoding schemes
  - Network security and protocol analysis
  - CTF challenges and capture techniques
  - Penetration testing methodologies
  - Defensive security and incident response

## Installation

### Using Ollama

```bash
# Create the SHARK model
ollama create shark -f model/Modelfile

# Run SHARK
ollama run shark
```

### Using OpenCode

```bash
# Install dependencies
pip install opencode

# Launch SHARK with OpenCode
.\scripts\launch_shark.bat
```

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/webcrawler.py` | Web crawler for security research |
| `scripts/shark_launch.py` | OpenCode launch configuration |
| `scripts\launch_shark.bat` | Windows batch launcher for OpenCode |

## Internal Tools (SHARK's self-extension workspace)

SHARK can author its own reusable skills and tools in `internaltools/`. The folder is
registered in the root `opencode.json` as an instruction file and a skills source, so
OpenCode advertises the skills to SHARK automatically.

```
internaltools/
├── AGENTS.md           # Convention loaded into SHARK's context
├── registry.json       # Catalog of authored skills and tools
├── skills/             # SHARK-authored skills (SKILL.md files)
├── tools/              # SHARK-authored executable tools
└── templates/          # Starting points for new skills and tools
```

When SHARK needs a repeatable capability, it checks the registry, adds a skill or tool
under `internaltools/`, registers it, runs the validator, and reloads OpenCode. Validate
the workspace with:

```bash
python internaltools/tools/validate_internaltools.py
```

See `internaltools/README.md` and the `internal-tool-authoring` skill for details.

## Manual Knowledge (portable memory)

`manualknowledge/` stores durable, hand-maintained facts about you and your work. SHARK
loads `manualknowledge/AGENTS.md` at the start of every OpenCode session and uses the
`manual-knowledge` skill to save anything you ask it to remember.

```
manualknowledge/
├── AGENTS.md        # Rules loaded into SHARK's context
├── README.md        # Usage and sync instructions
├── profile.md       # Facts about you
├── preferences.md   # How you want SHARK to work
├── environment.md   # Machines, tools, paths (no credentials)
└── projects.md      # Project context and decisions
```

The folder is deliberately tracked by git so it can be pulled on another computer;
commit/push after changes (or let `sync-tide.sh` do it). Never store secrets there.

## Model Configuration

The Modelfile (`model/Modelfile`) has been upgraded from `qwen2.5:1.5b` to `qwen2.5:7b`
with optimized parameters for cybersecurity tasks:

```dockerfile
FROM qwen2.5:7b

PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER num_ctx 32768
PARAMETER num_predict 4096
PARAMETER num_thread 16

SYSTEM """You are SHARK, the SHARK Cybersecurity Assistant...
(Full system prompt omitted for brevity)"""
```

## Training

SHARK includes training scripts for further customization:

```bash
# Train SHARK on custom data
python training\train.py

# Prepare dataset
python training\prepare_dataset.py

# Evaluate model performance
python training\evaluate.py
```

## Web Crawling

SHARK includes a web crawler utility for security research:

```bash
# Basic crawl
python scripts\webcrawler.py https://example.com

# Crawl with security extraction
python scripts\webcrawler.py https://example.com --extract

# Output to file
python scripts\webcrawler.py https://example.com -o results.json
```

## GitHub Preparation

This project is ready for GitHub with:

- Clean `.gitignore` configuration
- Comprehensive `README.md` with installation instructions
- Organized `scripts/` directory
- Proper `model/` structure
- Training and evaluation pipeline
- Ethical security research boundaries clearly stated

## Ethical Use

SHARK is designed for authorized security research, penetration testing,
and defensive security only. Always operate within legal and ethical boundaries.
Never use SHARK for unauthorized access or malicious activities.