"""Prompt template for repository overview explanation."""

from .common import TOPICS_INSTRUCTIONS


def build_repo_prompt(
    tree: str,
    config_content: str | None = None,
    readme_content: str | None = None,
    entry_points: list[str] | None = None,
) -> str:
    """
    Build prompt for explaining a repository's architecture.

    Args:
        tree: Directory tree string
        config_content: pyproject.toml / package.json / Cargo.toml content
        readme_content: README content if present
        entry_points: List of identified entry point files
    """
    sections = [
        "You are a senior software engineer explaining a codebase to a new team member.",
        "Provide a clear, structured overview of this repository.",
        "",
        "## Directory Structure",
        "",
        "```",
        tree,
        "```",
    ]

    if config_content:
        sections.extend([
            "",
            "## Project Configuration",
            "",
            "```",
            config_content,
            "```",
        ])

    if readme_content:
        sections.extend([
            "",
            "## README",
            "",
            readme_content,
        ])

    if entry_points:
        sections.extend([
            "",
            "## Entry Points",
            "",
        ])
        for ep in entry_points:
            sections.append(f"- {ep}")

    sections.extend([
        "",
        "## Instructions",
        "",
        "Write a comprehensive overview covering:",
        "",
        "1. **Purpose**: What does this project do? What problem does it solve?",
        "2. **Architecture**: High-level architecture and design patterns used",
        "3. **Key Components**: The most important modules/packages and their roles",
        "4. **Data Flow**: How data flows through the system",
        "5. **Dependencies**: Notable external dependencies and why they're used",
        "6. **Entry Points**: How the application is started/invoked",
        "7. **Configuration**: How the project is configured",
        "",
        "Format your response as markdown with clear sections and headers.",
        "Be specific — reference actual file and directory names from the tree.",
        "Focus on helping someone new understand the codebase quickly.",
        TOPICS_INSTRUCTIONS,
    ])

    return "\n".join(sections)
