"""Tests for code-explainer CLI."""

import json
import os
import tempfile

from click.testing import CliRunner

from code_explainer.cli import cli, _sanitize_path_for_filename, _find_project_config
from code_explainer.git_utils import extract_symbol, get_repo_structure, get_imports
from code_explainer.topics import (
    Topic,
    add_topics,
    load_queue,
    parse_topics_from_response,
    pending_count,
    pop_next,
    save_queue,
    skip_topic,
)


def test_cli_help():
    """CLI loads and shows help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AI-powered code explanation tool" in result.output


def test_cli_version():
    """CLI shows version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_subcommands_exist():
    """All subcommands are registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert "file" in result.output
    assert "function" in result.output
    assert "repo" in result.output
    assert "diff" in result.output
    assert "topics" in result.output
    assert "next" in result.output


def test_file_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["file", "--help"])
    assert result.exit_code == 0
    assert "Explain a file" in result.output


def test_function_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["function", "--help"])
    assert result.exit_code == 0
    assert "function or class" in result.output


def test_repo_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["repo", "--help"])
    assert result.exit_code == 0
    assert "repository" in result.output.lower()


def test_diff_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", "--help"])
    assert result.exit_code == 0
    assert "diff" in result.output.lower()


def test_topics_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["topics", "--help"])
    assert result.exit_code == 0
    assert "exploration queue" in result.output.lower()


def test_next_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["next", "--help"])
    assert result.exit_code == 0
    assert "next topic" in result.output.lower()


def test_sanitize_path():
    assert _sanitize_path_for_filename("src/auth/client.py") == "src-auth-client"
    assert _sanitize_path_for_filename("main.py") == "main"
    assert _sanitize_path_for_filename("a/b/c.rs") == "a-b-c"


def test_extract_symbol():
    """Test function extraction from source code."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            'def hello(name):\n'
            '    """Say hello."""\n'
            '    return f"Hello, {name}!"\n'
            '\n'
            'def goodbye():\n'
            '    return "bye"\n'
        )
        f.flush()

        result = extract_symbol(f.name, "hello")
        assert result is not None
        assert "def hello" in result
        assert "Hello" in result

        result2 = extract_symbol(f.name, "goodbye")
        assert result2 is not None
        assert "def goodbye" in result2

        result3 = extract_symbol(f.name, "nonexistent")
        assert result3 is None

        os.unlink(f.name)


def test_extract_class():
    """Test class extraction."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            'class MyClass:\n'
            '    def __init__(self):\n'
            '        self.x = 1\n'
            '\n'
            '    def method(self):\n'
            '        return self.x\n'
            '\n'
            'other_var = 42\n'
        )
        f.flush()

        result = extract_symbol(f.name, "MyClass")
        assert result is not None
        assert "class MyClass" in result
        assert "__init__" in result
        assert "method" in result

        os.unlink(f.name)


def test_get_repo_structure():
    """Test directory tree generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some structure
        os.makedirs(os.path.join(tmpdir, "src", "pkg"))
        with open(os.path.join(tmpdir, "src", "pkg", "main.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(tmpdir, "README.md"), "w") as f:
            f.write("# Hello")

        tree = get_repo_structure(tmpdir, max_depth=3)
        assert "src" in tree
        assert "main.py" in tree
        assert "README.md" in tree


def test_get_repo_structure_skips_hidden():
    """Test that .git and __pycache__ are filtered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git", "objects"))
        os.makedirs(os.path.join(tmpdir, "__pycache__"))
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src", "app.py"), "w") as f:
            f.write("")

        tree = get_repo_structure(tmpdir)
        assert ".git" not in tree
        assert "__pycache__" not in tree
        assert "src" in tree


def test_find_project_config():
    """Test project config detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
            f.write('[project]\nname = "test"\n')

        name, content = _find_project_config(tmpdir)
        assert name == "pyproject.toml"
        assert "test" in content


def test_function_requires_colon():
    """Function command requires FILE:SYMBOL format."""
    runner = CliRunner()
    result = runner.invoke(cli, ["function", "nocolon"])
    assert result.exit_code != 0
    assert "FILE_PATH:SYMBOL_NAME" in result.output


# --- Topics queue tests ---


def test_parse_topics_from_response():
    """Parse structured topics from model output."""
    response = """
# Explanation

Here is the explanation of the file.

## Topics to Explore

- [file] `src/workflow/executor.py` — Orchestrates the plan-execute-synthesize loop
- [function] `src/router.py:route_request` — Decides which agent handles each request
- [general] `error-handling-strategy` — How failures propagate across agent boundaries
"""
    topics = parse_topics_from_response(response, source="test")
    assert len(topics) == 3

    assert topics[0].kind == "file"
    assert topics[0].target == "src/workflow/executor.py"
    assert "plan-execute-synthesize" in topics[0].title
    assert topics[0].source == "test"

    assert topics[1].kind == "function"
    assert topics[1].target == "src/router.py:route_request"

    assert topics[2].kind == "general"
    assert topics[2].target == "error-handling-strategy"


def test_parse_topics_no_section():
    """No topics section means empty list."""
    response = "Just a plain explanation with no topics section."
    topics = parse_topics_from_response(response)
    assert topics == []


def test_parse_topics_alternate_header():
    """Handles 'Topic to Explore' (singular) header."""
    response = """
## Topic to Explore

- [file] `main.py` — Entry point
"""
    topics = parse_topics_from_response(response)
    assert len(topics) == 1
    assert topics[0].target == "main.py"


def test_queue_save_load():
    """Queue round-trips through JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = [
            Topic(title="Test topic", kind="file", target="src/main.py"),
            Topic(title="Another", kind="function", target="src/app.py:run"),
        ]
        save_queue(tmpdir, queue)

        loaded = load_queue(tmpdir)
        assert len(loaded) == 2
        assert loaded[0].title == "Test topic"
        assert loaded[0].kind == "file"
        assert loaded[1].target == "src/app.py:run"


def test_queue_empty_dir():
    """Loading from empty dir returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assert load_queue(tmpdir) == []


def test_add_topics_deduplicates():
    """Adding topics skips duplicates by target."""
    with tempfile.TemporaryDirectory() as tmpdir:
        t1 = Topic(title="First", kind="file", target="src/a.py")
        t2 = Topic(title="Second", kind="file", target="src/b.py")
        t3 = Topic(title="Duplicate", kind="file", target="src/a.py")

        added = add_topics(tmpdir, [t1, t2])
        assert added == 2

        added = add_topics(tmpdir, [t3])
        assert added == 0

        queue = load_queue(tmpdir)
        assert len(queue) == 2


def test_pop_next():
    """Pop returns first pending and marks it done."""
    with tempfile.TemporaryDirectory() as tmpdir:
        topics = [
            Topic(title="First", kind="file", target="a.py"),
            Topic(title="Second", kind="file", target="b.py"),
        ]
        save_queue(tmpdir, topics)

        topic = pop_next(tmpdir)
        assert topic is not None
        assert topic.target == "a.py"
        assert topic.status == "done"

        # Queue on disk should reflect the change
        queue = load_queue(tmpdir)
        assert queue[0].status == "done"
        assert queue[1].status == "pending"

        # Pop again gets second
        topic2 = pop_next(tmpdir)
        assert topic2.target == "b.py"

        # Pop on empty returns None
        assert pop_next(tmpdir) is None


def test_skip_topic():
    """Skip marks a pending topic as skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        topics = [
            Topic(title="First", kind="file", target="a.py"),
            Topic(title="Second", kind="file", target="b.py"),
            Topic(title="Third", kind="file", target="c.py"),
        ]
        save_queue(tmpdir, topics)

        # Skip first pending (index 0)
        assert skip_topic(tmpdir, 0) is True

        queue = load_queue(tmpdir)
        assert queue[0].status == "skipped"
        assert queue[1].status == "pending"

        # Pending count should be 2
        assert pending_count(tmpdir) == 2


def test_pending_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert pending_count(tmpdir) == 0

        topics = [
            Topic(title="A", kind="file", target="a.py"),
            Topic(title="B", kind="file", target="b.py", status="done"),
        ]
        save_queue(tmpdir, topics)
        assert pending_count(tmpdir) == 1


def test_topics_subcommand_empty():
    """Topics command shows message when queue is empty."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(cli, ["topics", "-d", tmpdir])
        assert result.exit_code == 0
        assert "No topics queued" in result.output


def test_topics_subcommand_with_items():
    """Topics command lists pending items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        topics = [
            Topic(title="Executor module", kind="file", target="src/executor.py", source="repo-overview"),
            Topic(title="Router logic", kind="function", target="src/router.py:route", source="repo-overview"),
        ]
        save_queue(tmpdir, topics)

        runner = CliRunner()
        result = runner.invoke(cli, ["topics", "-d", tmpdir])
        assert result.exit_code == 0
        assert "src/executor.py" in result.output
        assert "src/router.py:route" in result.output
        assert "2 pending" in result.output


def test_next_subcommand_empty():
    """Next command shows message when queue is empty."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(cli, ["next", "-d", tmpdir])
        assert result.exit_code == 0
        assert "No pending topics" in result.output


def test_next_skip():
    """Next --skip marks the next topic as skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        topics = [
            Topic(title="First", kind="file", target="a.py"),
            Topic(title="Second", kind="file", target="b.py"),
        ]
        save_queue(tmpdir, topics)

        runner = CliRunner()
        result = runner.invoke(cli, ["next", "--skip", "-d", tmpdir])
        assert result.exit_code == 0
        assert "Skipped" in result.output

        queue = load_queue(tmpdir)
        assert queue[0].status == "skipped"
        assert queue[1].status == "pending"
