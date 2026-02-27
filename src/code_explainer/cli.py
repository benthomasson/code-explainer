"""Command-line interface for code explanation."""

import asyncio
import os
import sys

import click

from .explainer import check_model_available, explain
from .git_utils import (
    extract_symbol,
    find_related_tests,
    get_commit_log,
    get_diff,
    get_file_content,
    get_imports,
    get_repo_structure,
)
from .prompts import (
    build_diff_prompt,
    build_file_prompt,
    build_function_prompt,
    build_repo_prompt,
)
from .topics import (
    add_topics,
    load_queue,
    parse_topics_from_response,
    pending_count,
    pop_next,
    skip_topic,
)


def _sanitize_path_for_filename(path: str) -> str:
    """Convert a file path to a safe filename (e.g., src/auth/client.py -> src-auth-client)."""
    name = path.replace("/", "-").replace("\\", "-")
    # Remove extension
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def _save_output(content: str, output_path: str) -> None:
    """Save content to a file, creating directories as needed."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def _enqueue_topics(response: str, source: str, output_dir: str) -> None:
    """Parse topics from model response and add to queue."""
    new_topics = parse_topics_from_response(response, source=source)
    if new_topics:
        added = add_topics(output_dir, new_topics)
        if added:
            total = pending_count(output_dir)
            click.echo(f"Queued {added} new topic(s) ({total} pending)", err=True)


def _find_project_config(repo_path: str) -> tuple[str | None, str | None]:
    """Find and read the project config file (pyproject.toml, package.json, etc.)."""
    config_files = [
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "Makefile",
    ]
    for config in config_files:
        path = os.path.join(repo_path, config)
        content = get_file_content(path)
        if content is not None:
            return config, content
    return None, None


def _find_entry_points(repo_path: str, config_content: str | None) -> list[str]:
    """Identify likely entry points from config and convention."""
    entry_points = []

    # Check common entry point patterns
    candidates = [
        "src/main.py",
        "main.py",
        "app.py",
        "src/app.py",
        "manage.py",
        "setup.py",
        "cli.py",
    ]
    for candidate in candidates:
        if os.path.isfile(os.path.join(repo_path, candidate)):
            entry_points.append(candidate)

    # Parse pyproject.toml entry points
    if config_content and "[project.scripts]" in config_content:
        in_scripts = False
        for line in config_content.split("\n"):
            if "[project.scripts]" in line:
                in_scripts = True
                continue
            if in_scripts:
                if line.startswith("["):
                    break
                if "=" in line:
                    entry_points.append(line.strip())

    return entry_points


@click.group()
@click.version_option()
def cli():
    """AI-powered code explanation tool."""
    pass


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--model",
    "-m",
    default="claude",
    help="Model to use (default: claude)",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Repository root (default: current directory)",
)
def file(file_path, model, output_dir, repo):
    """Explain a file's purpose, structure, and key patterns."""
    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    abs_path = os.path.abspath(file_path)
    content = get_file_content(abs_path)
    if content is None:
        click.echo(f"Error: Cannot read file: {file_path}", err=True)
        sys.exit(1)

    click.echo(f"Explaining {file_path}...", err=True)

    # Gather context
    rel_path = os.path.relpath(abs_path, os.path.abspath(repo))
    import_info = get_imports(abs_path, os.path.abspath(repo))
    repo_tree = get_repo_structure(os.path.abspath(repo), max_depth=2)

    # Build prompt
    prompt = build_file_prompt(
        file_path=rel_path,
        file_content=content,
        imports=import_info["imports"] or None,
        imported_by=import_info["imported_by"] or None,
        repo_context=repo_tree,
    )

    # Run model
    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Save output
    output_name = _sanitize_path_for_filename(rel_path) + ".md"
    output_path = os.path.join(output_dir, output_name)
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    # Enqueue follow-up topics
    _enqueue_topics(result, source=f"file:{rel_path}", output_dir=output_dir)

    click.echo(result)


@cli.command()
@click.argument("target")
@click.option(
    "--model",
    "-m",
    default="claude",
    help="Model to use (default: claude)",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Repository root (default: current directory)",
)
def function(target, model, output_dir, repo):
    """
    Explain a specific function or class.

    TARGET should be in the format FILE_PATH:SYMBOL_NAME
    (e.g., src/auth/client.py:login)
    """
    if ":" not in target:
        click.echo("Error: TARGET must be FILE_PATH:SYMBOL_NAME (e.g., src/auth.py:login)", err=True)
        sys.exit(1)

    file_path, symbol_name = target.rsplit(":", 1)

    if not os.path.isfile(file_path):
        click.echo(f"Error: File not found: {file_path}", err=True)
        sys.exit(1)

    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    abs_path = os.path.abspath(file_path)
    abs_repo = os.path.abspath(repo)

    # Extract symbol
    symbol_source = extract_symbol(abs_path, symbol_name)
    if symbol_source is None:
        click.echo(f"Error: Symbol '{symbol_name}' not found in {file_path}", err=True)
        sys.exit(1)

    click.echo(f"Explaining {symbol_name} from {file_path}...", err=True)

    # Get full file for context
    full_content = get_file_content(abs_path)

    # Find related tests
    related_tests = find_related_tests(abs_path, abs_repo, symbol_name)

    # Build prompt
    rel_path = os.path.relpath(abs_path, abs_repo)
    prompt = build_function_prompt(
        file_path=rel_path,
        symbol_name=symbol_name,
        symbol_source=symbol_source,
        full_file_content=full_content,
        related_tests=related_tests or None,
    )

    # Run model
    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Save output
    output_name = _sanitize_path_for_filename(rel_path) + f"-{symbol_name}.md"
    output_path = os.path.join(output_dir, output_name)
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    # Enqueue follow-up topics
    _enqueue_topics(result, source=f"function:{rel_path}:{symbol_name}", output_dir=output_dir)

    click.echo(result)


@cli.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
)
@click.option(
    "--model",
    "-m",
    default="claude",
    help="Model to use (default: claude)",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
def repo(repo_path, model, output_dir):
    """Generate a high-level repository architecture overview."""
    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    abs_repo = os.path.abspath(repo_path)
    click.echo(f"Analyzing repository at {abs_repo}...", err=True)

    # Gather repo info
    tree = get_repo_structure(abs_repo)

    config_name, config_content = _find_project_config(abs_repo)
    if config_name:
        click.echo(f"Found config: {config_name}", err=True)

    readme_path = os.path.join(abs_repo, "README.md")
    readme_content = get_file_content(readme_path)
    if readme_content is None:
        # Try README.rst, README.txt, README
        for alt in ["README.rst", "README.txt", "README"]:
            readme_content = get_file_content(os.path.join(abs_repo, alt))
            if readme_content is not None:
                break

    entry_points = _find_entry_points(abs_repo, config_content)

    # Build prompt
    prompt = build_repo_prompt(
        tree=tree,
        config_content=config_content,
        readme_content=readme_content,
        entry_points=entry_points or None,
    )

    # Run model
    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Save output
    output_path = os.path.join(output_dir, "repo-overview.md")
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    # Enqueue follow-up topics
    _enqueue_topics(result, source="repo-overview", output_dir=output_dir)

    click.echo(result)


@cli.command()
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Branch to explain (default: staged changes)",
)
@click.option(
    "--base",
    default="main",
    help="Base branch to diff against (default: main)",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Repository root (default: current directory)",
)
@click.option(
    "--model",
    "-m",
    default="claude",
    help="Model to use (default: claude)",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
def diff(branch, base, repo, model, output_dir):
    """Explain what changed in a diff and why."""
    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    abs_repo = os.path.abspath(repo)

    # Get diff
    try:
        if branch:
            diff_content = get_diff(branch, base, cwd=abs_repo)
        else:
            diff_content = get_diff(cwd=abs_repo)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not diff_content.strip():
        click.echo("No changes to explain.", err=True)
        sys.exit(0)

    # Get commit log
    commit_log = None
    if branch:
        commit_log = get_commit_log(branch, base, cwd=abs_repo)

    # Extract changed files
    changed_files = []
    for line in diff_content.split("\n"):
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                changed_files.append(path)

    diff_label = branch or "staged"
    click.echo(f"Explaining {diff_label} changes ({len(changed_files)} files)...", err=True)

    # Build prompt
    prompt = build_diff_prompt(
        diff_content=diff_content,
        commit_log=commit_log,
        changed_files_summary=changed_files or None,
    )

    # Run model
    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Save output
    safe_label = diff_label.replace("/", "-")
    output_path = os.path.join(output_dir, f"diff-{safe_label}.md")
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    # Enqueue follow-up topics
    _enqueue_topics(result, source=f"diff:{diff_label}", output_dir=output_dir)

    click.echo(result)


@cli.command()
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Show all topics including done and skipped",
)
def topics(output_dir, show_all):
    """Show the exploration queue."""
    queue = load_queue(output_dir)

    if not queue:
        click.echo("No topics queued. Run an explanation to discover topics.")
        return

    pending = [t for t in queue if t.status == "pending"]
    done = [t for t in queue if t.status == "done"]
    skipped = [t for t in queue if t.status == "skipped"]

    if pending:
        click.echo(f"Pending ({len(pending)}):\n")
        for i, topic in enumerate(pending):
            click.echo(f"  {i}. [{topic.kind}] {topic.target}")
            click.echo(f"     {topic.title}")
            if topic.source:
                click.echo(f"     (from {topic.source})")
            click.echo()
    else:
        click.echo("No pending topics.")

    if show_all:
        if done:
            click.echo(f"Done ({len(done)}):\n")
            for topic in done:
                click.echo(f"  [{topic.kind}] {topic.target} - {topic.title}")
        if skipped:
            click.echo(f"\nSkipped ({len(skipped)}):\n")
            for topic in skipped:
                click.echo(f"  [{topic.kind}] {topic.target} - {topic.title}")

    click.echo(f"\n{len(pending)} pending, {len(done)} done, {len(skipped)} skipped")


@cli.command("next")
@click.option(
    "--model",
    "-m",
    default="claude",
    help="Model to use (default: claude)",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    default="./explanations",
    help="Output directory (default: ./explanations/)",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Repository root (default: current directory)",
)
@click.option(
    "--skip",
    is_flag=True,
    default=False,
    help="Skip the next topic instead of explaining it",
)
def next_topic(model, output_dir, repo, skip):
    """Explain the next topic in the exploration queue."""
    if skip:
        if skip_topic(output_dir, 0):
            # Show what's next now
            queue = load_queue(output_dir)
            pending = [t for t in queue if t.status == "pending"]
            if pending:
                click.echo(f"Skipped. Next: [{pending[0].kind}] {pending[0].target}")
            else:
                click.echo("Skipped. No more pending topics.")
        else:
            click.echo("Nothing to skip.")
        return

    topic = pop_next(output_dir)
    if topic is None:
        click.echo("No pending topics. Run an explanation to discover topics.")
        return

    click.echo(f"Next topic: [{topic.kind}] {topic.target}", err=True)
    click.echo(f"  {topic.title}", err=True)
    if topic.source:
        click.echo(f"  (surfaced by {topic.source})", err=True)
    click.echo(err=True)

    abs_repo = os.path.abspath(repo)

    # Dispatch based on topic kind
    if topic.kind == "file":
        _run_file_topic(topic, model, output_dir, abs_repo)
    elif topic.kind == "function":
        _run_function_topic(topic, model, output_dir, abs_repo)
    elif topic.kind == "repo":
        _run_repo_topic(topic, model, output_dir, abs_repo)
    elif topic.kind == "diff":
        _run_diff_topic(topic, model, output_dir, abs_repo)
    elif topic.kind == "general":
        _run_general_topic(topic, model, output_dir, abs_repo)
    else:
        click.echo(f"Unknown topic kind: {topic.kind}", err=True)
        sys.exit(1)

    remaining = pending_count(output_dir)
    if remaining:
        click.echo(f"\n{remaining} topic(s) remaining. Run `explain next` to continue.", err=True)
    else:
        click.echo("\nNo more topics. Exploration complete.", err=True)


def _run_file_topic(topic, model, output_dir, repo_path):
    """Handle a file exploration topic."""
    # Target is a file path, possibly relative to repo
    file_path = topic.target
    abs_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path

    if not os.path.isfile(abs_path):
        click.echo(f"File not found: {file_path} (skipping)", err=True)
        return

    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    content = get_file_content(abs_path)
    if content is None:
        click.echo(f"Cannot read file: {file_path}", err=True)
        return

    rel_path = os.path.relpath(abs_path, repo_path)
    import_info = get_imports(abs_path, repo_path)
    repo_tree = get_repo_structure(repo_path, max_depth=2)

    prompt = build_file_prompt(
        file_path=rel_path,
        file_content=content,
        imports=import_info["imports"] or None,
        imported_by=import_info["imported_by"] or None,
        repo_context=repo_tree,
    )

    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    output_name = _sanitize_path_for_filename(rel_path) + ".md"
    output_path = os.path.join(output_dir, output_name)
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    _enqueue_topics(result, source=f"file:{rel_path}", output_dir=output_dir)
    click.echo(result)


def _run_function_topic(topic, model, output_dir, repo_path):
    """Handle a function exploration topic."""
    # Target should be file:symbol
    if ":" not in topic.target:
        click.echo(f"Function topic target must be file:symbol, got: {topic.target}", err=True)
        return

    file_path, symbol_name = topic.target.rsplit(":", 1)
    abs_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path

    if not os.path.isfile(abs_path):
        click.echo(f"File not found: {file_path} (skipping)", err=True)
        return

    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    symbol_source = extract_symbol(abs_path, symbol_name)
    if symbol_source is None:
        click.echo(f"Symbol '{symbol_name}' not found in {file_path} (skipping)", err=True)
        return

    full_content = get_file_content(abs_path)
    related_tests = find_related_tests(abs_path, repo_path, symbol_name)
    rel_path = os.path.relpath(abs_path, repo_path)

    prompt = build_function_prompt(
        file_path=rel_path,
        symbol_name=symbol_name,
        symbol_source=symbol_source,
        full_file_content=full_content,
        related_tests=related_tests or None,
    )

    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    output_name = _sanitize_path_for_filename(rel_path) + f"-{symbol_name}.md"
    output_path = os.path.join(output_dir, output_name)
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    _enqueue_topics(result, source=f"function:{rel_path}:{symbol_name}", output_dir=output_dir)
    click.echo(result)


def _run_repo_topic(topic, model, output_dir, repo_path):
    """Handle a repo exploration topic."""
    # For repo topics, target might be a subdirectory or the whole repo
    target_path = os.path.join(repo_path, topic.target) if topic.target != "." else repo_path

    if not os.path.isdir(target_path):
        target_path = repo_path

    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    tree = get_repo_structure(target_path)
    config_name, config_content = _find_project_config(target_path)
    readme_content = get_file_content(os.path.join(target_path, "README.md"))
    entry_points = _find_entry_points(target_path, config_content)

    prompt = build_repo_prompt(
        tree=tree,
        config_content=config_content,
        readme_content=readme_content,
        entry_points=entry_points or None,
    )

    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    output_path = os.path.join(output_dir, "repo-overview.md")
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    _enqueue_topics(result, source="repo-overview", output_dir=output_dir)
    click.echo(result)


def _run_diff_topic(topic, model, output_dir, repo_path):
    """Handle a diff exploration topic."""
    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    try:
        diff_content = get_diff(topic.target, cwd=repo_path)
    except RuntimeError as e:
        click.echo(f"Error getting diff: {e}", err=True)
        return

    if not diff_content.strip():
        click.echo("No changes to explain.", err=True)
        return

    commit_log = get_commit_log(topic.target, cwd=repo_path)

    changed_files = []
    for line in diff_content.split("\n"):
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                changed_files.append(path)

    prompt = build_diff_prompt(
        diff_content=diff_content,
        commit_log=commit_log,
        changed_files_summary=changed_files or None,
    )

    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    safe_label = topic.target.replace("/", "-")
    output_path = os.path.join(output_dir, f"diff-{safe_label}.md")
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    _enqueue_topics(result, source=f"diff:{topic.target}", output_dir=output_dir)
    click.echo(result)


def _run_general_topic(topic, model, output_dir, repo_path):
    """Handle a general exploration topic — uses repo context + the topic question."""
    if not check_model_available(model):
        click.echo(f"Error: Model '{model}' CLI not available", err=True)
        sys.exit(1)

    tree = get_repo_structure(repo_path, max_depth=3)
    config_name, config_content = _find_project_config(repo_path)

    from .prompts import TOPICS_INSTRUCTIONS

    prompt = "\n".join([
        "You are a senior software engineer explaining a codebase to a new team member.",
        f"The reader wants to understand: **{topic.title}**",
        "",
        "## Repository Structure",
        "",
        "```",
        tree,
        "```",
        "",
    ])

    if config_content:
        prompt += "\n".join([
            "## Project Configuration",
            "",
            "```",
            config_content,
            "```",
            "",
        ])

    prompt += "\n".join([
        "",
        "## Instructions",
        "",
        f"Explain **{topic.title}** in the context of this codebase.",
        "Reference specific files, modules, and patterns.",
        "If you can identify the relevant source files, include key code snippets.",
        "",
        "Format your response as markdown.",
        TOPICS_INSTRUCTIONS,
    ])

    click.echo(f"Running {model}...", err=True)
    try:
        result = asyncio.run(explain(prompt, model))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    safe_label = _sanitize_path_for_filename(topic.target)
    output_path = os.path.join(output_dir, f"topic-{safe_label}.md")
    _save_output(result, output_path)
    click.echo(f"Saved to {output_path}", err=True)

    _enqueue_topics(result, source=f"general:{topic.target}", output_dir=output_dir)
    click.echo(result)


@cli.command("install-skill")
@click.option(
    "--skill-dir",
    type=click.Path(),
    default=None,
    help="Target directory for skill file (default: .claude/skills/code-explainer)",
)
def install_skill(skill_dir):
    """Install the code-explainer skill file for Claude Code."""
    from pathlib import Path

    from .skill import get_skill_content

    if skill_dir:
        target_dir = Path(skill_dir)
    else:
        target_dir = Path.cwd() / ".claude" / "skills" / "code-explainer"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "SKILL.md"

    target_file.write_text(get_skill_content())
    click.echo(f"Installed skill to {target_file}")


if __name__ == "__main__":
    cli()
