"""Thin wrapper around the Anthropic SDK with cached system prompts.

Each pipeline stage that calls the LLM gets one of these. The system block is
the stage's stable instruction set (schema + extraction guidance); the user
block is the per-call payload (one paper, one claim pair, etc.). Caching the
system block matters most at stage 5, where N×M variant-pair scoring calls
share the same rubric.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from .config import DEFAULT_MODEL

# override=True so a .env value beats an empty/stale ANTHROPIC_API_KEY inherited
# from the shell environment.
load_dotenv(override=True)

@dataclass
class LLM:
    model: str = DEFAULT_MODEL
    client: Anthropic = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.client is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set — copy .env.example to .env and fill it in"
                )
            # max_retries=8 lets the SDK's exponential-backoff + Retry-After
            # logic ride out sustained 429s when several large PDFs hit the
            # per-minute token rate limit back to back. Default is 2 (too few).
            self.client = Anthropic(api_key=api_key, max_retries=8)

    def complete(
        self,
        *,
        system: str,
        user: str | list[dict[str, Any]],
        max_tokens: int = 4096,
        cache_system: bool = True,
    ) -> str:
        """Single-turn convenience wrapper around chat()."""
        user_content: list[dict[str, Any]]
        if isinstance(user, str):
            user_content = [{"type": "text", "text": user}]
        else:
            user_content = user
        return self.chat(
            system=system,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=max_tokens,
            cache_system=cache_system,
        )

    def chat(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        cache_system: bool = True,
    ) -> str:
        """Multi-turn call. Pass a full Anthropic-style messages list.

        Use this when you need to feed the assistant's previous response back in
        — e.g. retry-with-feedback when the model's output failed validation.
        """
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        # Stream under the hood: the Anthropic SDK rejects non-streaming
        # requests whose max_tokens × per-token-rate could exceed 10 minutes.
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=messages,
        ) as stream:
            return stream.get_final_text()


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)
_FIRST_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_response(text: str) -> Any:
    """Parse a model response as JSON, tolerating code fences and stray prose.

    Strategy: try strict json.loads first; if that fails, strip ```json fencing;
    if that fails, find the first {...} block. Raises json.JSONDecodeError if
    nothing is parseable.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = _FENCE_RE.match(text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    obj_match = _FIRST_OBJECT_RE.search(text)
    if obj_match:
        return json.loads(obj_match.group(0))  # raises on failure

    raise json.JSONDecodeError("no JSON object found in response", text, 0)
