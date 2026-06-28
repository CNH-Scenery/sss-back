"""Thin wrapper over the Anthropic Messages API for generating trading code.

Supports an offline fixture mode (CODEGEN_FIXTURE=true) that returns a known-good
module without calling the API, so tests and demos run without an API key.
"""
import os
import re
from typing import Any

from app.services.code_contract import SYSTEM_PROMPT

DEFAULT_MODEL = "claude-opus-4-8"

# A known-good `decide` returned in fixture mode. Satisfies the contract: pure,
# null-safe (returns HOLD on missing data), returns BUY/SELL/HOLD.
FIXTURE_CODE = '''\
def decide(features: dict, position: dict | None = None) -> dict:
    try:
        ma5 = features.get("ma5")
        ma20 = features.get("ma20")
        rsi = features.get("rsi14")
        if ma5 is None or ma20 is None or rsi is None:
            return {"action": "HOLD", "size_ratio": 0.0, "reason": "데이터 부족", "indicators": {}}

        in_position = bool(position and position.get("in_position"))
        ind = {"ma5": ma5, "ma20": ma20, "rsi14": rsi}

        if not in_position and ma5 > ma20 and rsi < 70:
            return {"action": "BUY", "size_ratio": 0.3, "reason": "단기 MA 상향 + 과열 아님", "indicators": ind}
        if in_position and (ma5 < ma20 or rsi > 75):
            return {"action": "SELL", "size_ratio": 1.0, "reason": "추세 약화 또는 과열", "indicators": ind}
        return {"action": "HOLD", "size_ratio": 0.0, "reason": "관망", "indicators": ind}
    except Exception:
        return {"action": "HOLD", "size_ratio": 0.0, "reason": "오류", "indicators": {}}
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
