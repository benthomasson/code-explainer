"""Prompt template for function/class explanation."""

from .common import TOPICS_INSTRUCTIONS


def build_function_prompt(
    file_path: str,
    symbol_name: str,
    symbol_source: str,
    full_file_content: str | None = None,
    related_tests: list[str] | None = None,
) -> str:
    """
    Build prompt for explaining a specific function or class.

    Args:
        file_path: Path to the source file
        symbol_name: Name of the function or class
        symbol_source: Extracted source code of the symbol
        full_file_content: Full file for additional context
        related_tests: Paths to related test files
    """
    sections = [
        "You are a senior software engineer explaining code to a colleague.",
        f"Explain the following symbol `{symbol_name}` from `{file_path}`.",
        "",
        "## Source Code",
        "",
        "```python",
        symbol_source,
        "```",
        "",
    ]

    if full_file_content:
        sections.extend([
            "## Full File Context",
            "",
            f"The symbol is defined in `{file_path}`. Here is the full file for context:",
            "",
            "```python",
            full_file_content,
            "```",
            "",
        ])

    if related_tests:
        sections.extend([
            "## Related Tests",
            "",
        ])
        for test in related_tests:
            sections.append(f"- `{test}`")
        sections.append("")

    sections.extend([
        "## Instructions",
        "",
        "Explain this function/class covering:",
        "",
        "1. **Purpose**: What does it do and why does it exist?",
        "2. **Parameters**: What each parameter means and expected types/values",
        "3. **Return Value**: What it returns and when",
        "4. **Algorithm**: Step-by-step walkthrough of the logic",
        "5. **Side Effects**: Any mutations, I/O, or state changes",
        "6. **Error Handling**: How errors are handled or propagated",
        "7. **Usage**: How this is typically called (based on context)",
        "",
        "Format your response as markdown.",
        "Be precise — explain the actual logic, not just paraphrase the code.",
        TOPICS_INSTRUCTIONS,
    ])

    return "\n".join(sections)
