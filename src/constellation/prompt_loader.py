"""Load prompt templates from src/constellation/prompts/."""
from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text()
