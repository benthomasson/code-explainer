"""Prompt templates for code explanation."""

from .common import TOPICS_INSTRUCTIONS
from .diff import build_diff_prompt
from .file import build_file_prompt
from .function import build_function_prompt
from .repo import build_repo_prompt

__all__ = [
    "build_file_prompt",
    "build_function_prompt",
    "build_repo_prompt",
    "build_diff_prompt",
    "TOPICS_INSTRUCTIONS",
]
