# code-explainer

AI-powered code explanation tool for onboarding onto unfamiliar codebases.

## Install

```bash
uv tool install git+https://github.com/benthomasson/code-explainer
```

## Usage

```bash
# Explain a repository's architecture
explain repo ~/git/some-project

# Explain a specific file
explain file src/auth/client.py

# Explain a specific function or class
explain function src/auth/client.py:login

# Explain a diff
explain diff -b feature-branch --base main
```

## Options

- `--model/-m`: Model to use (default: claude)
- `--output-dir/-d`: Output directory (default: ./explanations/)
- `--repo/-r`: Repository path (default: cwd)
