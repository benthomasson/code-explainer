"""Shared prompt components."""

# Appended to every prompt so the model surfaces follow-up explorations.
TOPICS_INSTRUCTIONS = """
## Topics to Explore

After your explanation, add a section titled "## Topics to Explore".
List 3-5 things the reader should explore next to deepen their understanding.
Each item MUST use this exact format:

- [kind] `target` — Description

Where:
- **kind** is one of: file, function, repo, diff, general
- **target** is the exploration target:
  - For file: the file path (e.g., `src/auth/client.py`)
  - For function: file:symbol (e.g., `src/auth/client.py:login`)
  - For general: a short label (e.g., `dataverse-integration`)
- **Description** explains why this is worth exploring

Example:
- [file] `src/workflow/executor.py` — Orchestrates the plan-execute-synthesize loop
- [function] `src/router.py:route_request` — Decides which agent handles each request
- [general] `error-handling-strategy` — How failures propagate across agent boundaries
"""
