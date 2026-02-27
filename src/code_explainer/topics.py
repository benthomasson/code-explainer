"""Exploration topics queue.

Tracks what to explore next when understanding a codebase.
Each explanation can surface new topics; the queue connects
isolated explanations into a guided exploration session.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Topic:
    """A queued exploration topic."""

    # What to explore — human-readable label
    title: str
    # Type of exploration: file, function, repo, diff, or general
    kind: str
    # Target for the exploration (file path, file:symbol, branch, etc.)
    target: str
    # Why this was surfaced (which explanation generated it)
    source: str = ""
    # Status: pending, done, skipped
    status: str = "pending"
    # When it was added
    added: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


TOPIC_KINDS = {"file", "function", "repo", "diff", "general"}


def _queue_path(output_dir: str) -> str:
    return os.path.join(output_dir, "topics.json")


def load_queue(output_dir: str) -> list[Topic]:
    """Load the topics queue from disk."""
    path = _queue_path(output_dir)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Topic(**item) for item in data]


def save_queue(output_dir: str, queue: list[Topic]) -> None:
    """Save the topics queue to disk."""
    os.makedirs(output_dir, exist_ok=True)
    path = _queue_path(output_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in queue], f, indent=2)


def add_topics(output_dir: str, topics: list[Topic]) -> int:
    """
    Add topics to the queue, skipping duplicates by target.

    Returns number of new topics added.
    """
    queue = load_queue(output_dir)
    existing_targets = {t.target for t in queue}
    added = 0
    for topic in topics:
        if topic.target not in existing_targets:
            queue.append(topic)
            existing_targets.add(topic.target)
            added += 1
    if added:
        save_queue(output_dir, queue)
    return added


def pop_next(output_dir: str) -> Topic | None:
    """
    Get the next pending topic and mark it as done.

    Returns None if queue is empty or all done.
    """
    queue = load_queue(output_dir)
    for topic in queue:
        if topic.status == "pending":
            topic.status = "done"
            save_queue(output_dir, queue)
            return topic
    return None


def skip_topic(output_dir: str, index: int) -> bool:
    """Mark a topic as skipped by its index in the queue."""
    queue = load_queue(output_dir)
    pending = [i for i, t in enumerate(queue) if t.status == "pending"]
    if index < 0 or index >= len(pending):
        return False
    queue[pending[index]].status = "skipped"
    save_queue(output_dir, queue)
    return True


def pending_count(output_dir: str) -> int:
    """Count pending topics."""
    return sum(1 for t in load_queue(output_dir) if t.status == "pending")


# --- Parsing topics from model output ---

# Expected format in model output:
#
# ## Topics to Explore
#
# - [file] `src/workflow/executor.py` — How the plan executor dispatches tasks
# - [function] `src/router.py:route_request` — The routing logic for complexity levels
# - [general] Dataverse mart integration — How agents read/write to data marts

TOPIC_LINE_PATTERN = re.compile(
    r"^[-*]\s+"
    r"\[(\w+)\]\s+"       # [kind]
    r"`([^`]+)`"           # `target`
    r"\s*(?:—|-|:)\s*"    # separator
    r"(.+)$",              # title/description
    re.MULTILINE,
)


def parse_topics_from_response(response: str, source: str = "") -> list[Topic]:
    """
    Parse follow-up topics from a model response.

    Looks for a "Topics to Explore" section with structured items.
    """
    # Find the topics section
    section_match = re.search(
        r"#+\s*Topics?\s+to\s+Explore\s*\n(.*?)(?=\n#|\Z)",
        response,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []

    section_text = section_match.group(1)
    topics = []

    for match in TOPIC_LINE_PATTERN.finditer(section_text):
        kind = match.group(1).lower()
        target = match.group(2)
        title = match.group(3).strip()

        if kind not in TOPIC_KINDS:
            kind = "general"

        topics.append(Topic(
            title=title,
            kind=kind,
            target=target,
            source=source,
        ))

    return topics
