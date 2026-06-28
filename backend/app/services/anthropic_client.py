"""Thin wrapper over the Anthropic Messages API for generating trading code.

Supports an offline fixture mode (CODEGEN_FIXTURE=true) that returns a known-good
module without calling the API, so tests and demos run without an API key.
"""
import os
import re
from typing import Any

from app.services.code_contract import SYSTEM_PROMPT

DEFAULT_MODEL = "claude-opus-4-8"

# A known-good script returned in fixture mode. It satisfies the contract: runs with
# no arguments, fetches Upbit candles via httpx, and prints exactly "buy" or "reject".
FIXTURE_CODE = '''\
import httpx


def _decide() -> str:
    url = "https://api.upbit.com/v1/candles/minutes/15"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"market": "KRW-BTC", "count": 50})
            resp.raise_for_status()
            candles = resp.json()
    except Exception:
        return "reject"

    closes = [float(c["trade_price"]) for c in candles]
    if len(closes) < 20:
        return "reject"

    # Upbit returns newest-first; reverse to chronological order.
    closes = closes[::-1]
    short_ma = sum(closes[-5:]) / 5
    long_ma = sum(closes[-20:]) / 20
    return "buy" if short_ma > long_ma else "reject"


if __name__ == "__main__":
    print(_decide())
'''


def fixture_enabled() -> bool:
    return os.getenv("CODEGEN_FIXTURE", "false").strip().lower() in {"1", "true", "yes"}


def get_model() -> str:
    return os.getenv("CODEGEN_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _extract_code(text: str) -> str:
    """Pull the python source out of a ```python fenced block, falling back to raw text."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


class AnthropicCodeClient:
    """Generates trading-code modules from a conversation history of user/assistant turns."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or get_model()
        self._fixture = fixture_enabled()
        self._client = None
        if not self._fixture:
            import anthropic

            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    @property
    def model_name(self) -> str:
        return "fixture" if self._fixture else self.model

    def generate_code(self, history: list[dict[str, Any]]) -> str:
        """history is a list of {"role": "user"|"assistant", "content": str} turns."""
        if self._fixture:
            return FIXTURE_CODE

        response = self._client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=SYSTEM_PROMPT,
            messages=history,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _extract_code(text)
