#!/usr/bin/env python3
"""SHARK AI OpenCode Launch Command - replaces ollama launch."""

import subprocess
import sys
import os
import json
import argparse
from pathlib import Path


def load_opencode_config():
    """Load OpenCode configuration."""
    config_path = Path.home() / ".config" / "opencode" / "opencode.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    # Fallback to project config
    project_config = Path.cwd() / "opencode" / "opencode.json"
    if project_config.exists():
        try:
            with open(project_config, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    return None


def launch_opencode_with_shark(config_path=None, **kwargs):
    """Launch OpenCode configured for SHARK AI."""
    # Load config
    if config_path is None:
        config_path = Path.cwd() / "opencode" / "opencode.json"
    
    if not os.path.exists(config_path):
        print(f"[SHARK] OpenCode config not found at {config_path}")
        print("Creating default configuration...")
        config = {
            "defaultModel": "ollama/shark:latest",
            "models": {
                "ollama/shark:latest": {
                    "name": "SHARK",
                    "provider": "ollama",
                    "systemPrompt": "SHARK Cybersecurity Assistant"
                }
            }
        }
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    # Load existing or create config
    config = load_opencode_config()
    if config is None:
        config = {
            "defaultModel": "ollama/shark:latest",
            "models": {
                "ollama/shark:latest": {
                    "name": "SHARK",
                    "provider": "ollama",
                    "systemPrompt": "SHARK Cybersecurity Assistant"
                }
            }
        }
    
    # Update model config if needed
    if "ollama/shark:latest" not in config.get("models", {}):
        config.setdefault("models", {})["ollama/shark:latest"] = {
            "name": "SHARK",
            "provider": "ollama",
            "systemPrompt": "SHARK Cybersecurity Assistant"
        }
    
    # Build the opencode command
    cmd = [sys.executable, "-m", "opencode"]
    
    # Add model specification
    model_name = config.get("defaultModel", "ollama/shark:latest")
    # opencode typically uses --model or -m flag
    cmd.extend(["--model", model_name])
    
    # Pass through any additional kwargs
    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key}", str(value)])
    
    print(f"[SHARK] Launching OpenCode with SHARK model: {model_name}")
    print(f"[SHARK] Config: {config_path}")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[SHARK] OpenCode exited with error code: {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("[SHARK] OpenCode not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "opencode"], check=True)
        subprocess.run(cmd, check=True)
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="SHARK AI - Launch OpenCode")
    parser.add_argument("-m", "--model", default="ollama/shark:latest",
                        help="Model to use (default: ollama/shark:latest)")
    parser.add_argument("-p", "--prompt", help="Initial prompt to send to SHARK")
    parser.add_argument("-c", "--config", help="Path to OpenCode config file")
    parser.add_argument("--list-models", action="store_true",
                        help="List available models")
    parser.add_argument("--system-prompt", default="SHARK Cybersecurity Assistant",
                        help="System prompt for SHARK")
    
    args = parser.parse_args()

    # Keep config paths stable regardless of where the launcher was invoked from.
    os.chdir(Path(__file__).resolve().parents[1])

    # Update config with custom system prompt if provided
    config_path = args.config or os.path.join(os.getcwd(), "opencode", "opencode.json")
    
    config = {
        "defaultModel": args.model,
        "models": {
            args.model: {
                "name": "SHARK",
                "provider": "ollama",
                "systemPrompt": args.system_prompt
            }
        }
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"[SHARK] OpenCode configuration written to {config_path}")
    print(f"[SHARK] Using model: {args.model}")
    print(f"[SHARK] System prompt: {args.system_prompt}")
    
    if args.list_models:
        print("[SHARK] Available models:")
        print("  - ollama/shark:latest (SHARK Cybersecurity Assistant)")
        return 0
    
    # Launch OpenCode
    exit_code = launch_opencode_with_shark(
        config_path=config_path,
    )
    
    # If an initial prompt is provided, we could send it, but that's complex
    # For now, just launch OpenCode
    sys.exit(exit_code)


if __name__ == "__main__":
    main()