"""Thin wrapper over the Anthropic Messages API for generating trading code.

Supports an offline fixture mode (CODEGEN_FIXTURE=true) that returns a known-good
module without calling the API, so tests and demos run without an API key.
"""
import os
import re
from typing import Any

from app.services.code_contract import SYSTEM_PROMPT

DEFAULT_MODEL = "claude-opus-4-8"

# A known-good module returned in fixture mode. It satisfies the full contract:
# fetches Upbit candles via httpx and returns a validated decision dict.
FIXTURE_CODE = '''\
import httpx

_UNIT = {"15m": 15, "60m": 60}


def generate_signal(market: str, timeframe: str = "15m") -> dict:
    unit = _UNIT.get(timeframe, 15)
    url = f"https://api.upbit.com/v1/candles/minutes/{unit}"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"market": market, "count": 50})
            resp.raise_for_status()
            candles = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"action": "hold", "size_ratio": 0.0, "reason": f"fetch failed: {exc}", "indicators": {}}

    closes = [float(c["trade_price"]) for c in candles]
    if len(closes) < 20:
        return {"action": "hold", "size_ratio": 0.0, "reason": "insufficient data", "indicators": {}}

    # Upbit returns newest-first; reverse to chronological order.
    closes = closes[::-1]
    short_ma = sum(closes[-5:]) / 5
    long_ma = sum(closes[-20:]) / 20
    last = closes[-1]

    indicators = {"short_ma": short_ma, "long_ma": long_ma, "last": last}
    if short_ma > long_ma * 1.001:
        return {"action": "buy", "size_ratio": 0.2, "reason": "short MA crossed above long MA", "indicators": indicators}
    if short_ma < long_ma * 0.999:
        return {"action": "sell", "size_ratio": 0.2, "reason": "short MA crossed below long MA", "indicators": indicators}
    return {"action": "hold", "size_ratio": 0.0, "reason": "no clear trend", "indicators": indicators}
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
