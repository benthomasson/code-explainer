"""Embedded skill content for install-skill command."""

from pathlib import Path

# Read skill content from the bundled SKILL.md
_SKILL_PATH = Path(__file__).parent.parent.parent / ".claude" / "skills" / "code-explainer" / "SKILL.md"


def get_skill_content() -> str:
    """Get skill content, falling back to embedded version if file not found."""
    if _SKILL_PATH.is_file():
        return _SKILL_PATH.read_text()
    return _EMBEDDED_SKILL


# Fallback embedded copy
_EMBEDDED_SKILL = """\
---
name: code-explainer
description: AI-powered code explanation with exploration queue for codebase onboarding
argument-hint: "[repo|file|function|diff|topics|next] [options]"
allowed-tools: Bash(explain *), Bash(uv run explain *), Bash(uvx *code-explainer*), Read
---

You are running AI-powered code explanations using the `explain` CLI tool. This tool provides just-in-time education about unfamiliar codebases. Each explanation surfaces follow-up topics, building a connected exploration session rather than isolated documents.

## How to Run

Try these in order until one works:
1. `explain $ARGUMENTS` (if installed via `uv tool install`)
2. `uv run explain $ARGUMENTS` (if in the repo with pyproject.toml)
3. `uvx --from git+https://github.com/benthomasson/code-explainer explain $ARGUMENTS` (fallback)

## Exploration Workflow

```bash
explain repo ~/git/some-project    # start here
explain topics                      # see what was surfaced
explain next                        # explore next topic
explain next                        # keep going
explain next --skip                 # skip one
explain topics --all                # see progress
```

## Commands

- `repo [PATH]` — Repository architecture overview
- `file FILE` — Explain a file
- `function FILE:SYMBOL` — Explain a function or class
- `diff [-b BRANCH]` — Explain changes
- `topics [--all]` — Show exploration queue
- `next [--skip]` — Explain or skip next topic

## Common Options

- `-m, --model` — Model (default: claude)
- `-d, --output-dir` — Output dir (default: ./explanations/)
- `-r, --repo` — Repo root (default: cwd)
"""
