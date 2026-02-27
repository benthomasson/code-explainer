---
name: code-explainer
description: AI-powered code explanation with exploration queue for codebase onboarding
argument-hint: "[repo|file|function|diff|topics|next] [options]"
allowed-tools: Bash(explain *), Bash(uv run explain *), Bash(uvx *code-explainer*), Read
---

You are running AI-powered code explanations using the `explain` CLI tool. This tool provides just-in-time education about unfamiliar codebases. Each explanation surfaces follow-up topics, building a connected exploration session rather than isolated documents.

## Philosophy

With AI, anyone should be able to work on any codebase. Instead of weeks of ramp-up, developers need the right explanation at the right moment. This tool provides that.

## How to Run

Try these in order until one works:
1. `explain $ARGUMENTS` (if installed via `uv tool install`)
2. `uv run explain $ARGUMENTS` (if in the repo with pyproject.toml)
3. `uvx --from git+https://github.com/benthomasson/code-explainer explain $ARGUMENTS` (fallback)

## Exploration Workflow

The tool is designed for iterative exploration, not one-shot document generation:

```bash
# 1. Start with a repo overview — seeds the exploration queue
explain repo ~/git/some-project

# 2. See what topics were surfaced
explain topics

# 3. Explore the next topic (auto-dispatches to file/function/etc.)
explain next

# 4. Keep going — each explanation surfaces more topics
explain next
explain next

# 5. Skip topics you don't care about
explain next --skip

# 6. Check progress
explain topics --all
```

## Common Commands

### Explain a repository
```bash
explain repo ~/git/some-project
explain repo ~/git/some-project -m gemini
```

### Explain a specific file
```bash
explain file src/auth/client.py --repo ~/git/some-project
```

### Explain a function or class
```bash
explain function src/auth/client.py:login --repo ~/git/some-project
explain function src/router.py:ComplexityRouter --repo ~/git/some-project
```

### Explain a diff
```bash
explain diff -b feature-branch --base main --repo ~/git/some-project
explain diff  # staged changes in current repo
```

### View and manage the exploration queue
```bash
explain topics              # show pending topics
explain topics --all        # show pending + done + skipped
explain next                # explain next topic
explain next --skip         # skip next topic
```

## Command Reference

### `repo [REPO_PATH]`
Generate a high-level repository architecture overview.

### `file FILE_PATH`
Explain a file's purpose, structure, and key patterns. Gathers import graph and repo context automatically.

### `function FILE_PATH:SYMBOL`
Explain a specific function or class. Extracts the symbol source, finds related tests, includes full file context.

### `diff`
Explain what changed in a diff and why. Includes commit log and file-by-file breakdown.

Options:
- `-b, --branch` — Branch to explain (default: staged changes)
- `--base` — Base branch to diff against (default: main)

### `topics`
Show the exploration queue. Each explanation automatically enqueues follow-up topics.

Options:
- `--all` — Show done and skipped topics too

### `next`
Pull the next pending topic and explain it. Dispatches to the right handler (file, function, repo, diff, or general) based on the topic kind.

Options:
- `--skip` — Mark next topic as skipped instead of explaining it

## Common Options (all commands)

- `-m, --model` — Model to use (default: claude, also supports gemini)
- `-d, --output-dir` — Output directory (default: ./explanations/)
- `-r, --repo` — Repository root (default: current directory)

## The Exploration Queue

Every explanation includes a "Topics to Explore" section. These are automatically parsed and added to `explanations/topics.json`. The queue:

- **Deduplicates** — won't add the same target twice
- **Tracks source** — records which explanation surfaced each topic
- **Supports kinds** — file, function, repo, diff, general
- **Persists** — lives in the output directory between invocations

## After Any Command

- Summarize the key points from the explanation
- Note how many new topics were queued
- Suggest running `explain next` if there are pending topics
- If the user seems to be onboarding, suggest starting with `explain repo`
