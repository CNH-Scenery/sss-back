"""Single source of truth for the contract that LLM-generated trading code must satisfy.

The harness asks Claude to produce one Python module that fetches Upbit candle data
over httpx and returns a trading decision. Both the verifier and the prompt are derived
from the constants here so they never drift apart.
"""

ENTRYPOINT_NAME = "generate_signal"

# The exact signature the generated module must expose.
ENTRYPOINT_SIGNATURE = 'def generate_signal(market: str, timeframe: str = "15m") -> dict:'

# Imports the generated code is allowed to use. Anything else fails static_check.
ALLOWED_IMPORTS = {
    "httpx",
    "json",
    "math",
    "statistics",
    "datetime",
    "decimal",
    "typing",
    "pandas",
    "numpy",
}

# Symbols that are never allowed (filesystem, process, eval, dynamic import).
FORBIDDEN_NAMES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "importlib",
    "builtins",
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
}

ALLOWED_ACTIONS = ("buy", "sell", "hold")

# Sample input the verifier uses to actually run the generated function.
SAMPLE_MARKET = "KRW-BTC"
SAMPLE_TIMEFRAME = "15m"

SYSTEM_PROMPT = f"""You are a senior quant developer. You write a SINGLE self-contained Python module that decides a crypto trade based on Upbit market data.

HARD REQUIREMENTS — the module is rejected automatically if any are violated:
1. Define exactly this entrypoint (signature must match):
   {ENTRYPOINT_SIGNATURE}
2. Inside it, fetch candle data directly from Upbit's public REST API using `httpx`.
   - Endpoint example: GET https://api.upbit.com/v1/candles/minutes/15?market=KRW-BTC&count=100
   - Map `timeframe` "15m"->15, "60m"->60 for the minutes unit.
   - Upbit candle fields: opening_price, high_price, low_price, trade_price (close), candle_acc_trade_volume.
3. Compute indicators from the candles and return a decision dict EXACTLY shaped as:
   {{
     "action": "buy" | "sell" | "hold",
     "size_ratio": float,   # 0.0 to 1.0 inclusive; use 0.0 for hold
     "reason": str,         # short human-readable rationale
     "indicators": {{ ... }}  # optional: the indicator values you computed
   }}
4. ONLY import from this allowlist: {", ".join(sorted(ALLOWED_IMPORTS))}.
   NEVER import or call: {", ".join(sorted(FORBIDDEN_NAMES))}.
5. No top-level side effects: no network calls, prints, or execution at import time.
   All work happens inside `{ENTRYPOINT_NAME}`. A `if __name__ == "__main__":` guard is allowed but optional.
6. Handle errors defensively: set a short httpx timeout, and if data is insufficient, return action "hold".

OUTPUT FORMAT:
Return ONLY the Python source code inside a single ```python fenced code block. No prose before or after.
"""


def build_user_prompt(prompt: str, market: str, timeframe: str) -> str:
    """Wrap the user's natural-language strategy request with the concrete target market."""
    return (
        f"Write the trading module for this strategy request:\n\n{prompt}\n\n"
        f"It will be verified by calling {ENTRYPOINT_NAME}(\"{market}\", \"{timeframe}\")."
    )


def build_retry_prompt(errors: list[str], stage: str) -> str:
    """Feedback message appended after a failed verification attempt."""
    joined = "\n".join(f"- {e}" for e in errors) or "- (no detail captured)"
    return (
        f"The previous module FAILED verification at the '{stage}' stage:\n{joined}\n\n"
        "Fix these problems and return the full corrected module again as a single "
        "```python fenced code block. Keep the same entrypoint signature and contract."
    )
