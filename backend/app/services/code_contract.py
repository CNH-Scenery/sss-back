"""Single source of truth for the contract that LLM-generated trading code must satisfy.

The LLM produces ONE pure function:

    def decide(features: dict, position: dict | None = None) -> dict

`features` is a flat dict of pre-computed indicators (the backend computes them from
candles — for live: the latest bar; for backtest: each historical bar). The function
returns a BUY / SELL / HOLD decision. It must be null-safe: any missing/None feature
must yield HOLD rather than raising, so the frontend can call it for realtime
monitoring at any time.

The same function powers both the live monitor (WebSocket) and the backtester — only
the caller (data + loop) differs. Prompt, verifier, engine and backtester all derive
from the constants here so the format never drifts.
"""

ENTRYPOINT_NAME = "decide"
ENTRYPOINT_SIGNATURE = "def decide(features: dict, position: dict | None = None) -> dict:"

# The decision vocabulary (uppercase, matching the frontend).
DECISIONS = ("BUY", "SELL", "HOLD")

# The exact feature keys the backend provides and the function may read.
# Keep in lockstep with feature_engine.py and the frontend feature snapshot.
FEATURE_KEYS = [
    "close",              # latest close price
    "rsi14",              # RSI(14), 0-100
    "vol_ratio",          # volume / 20-bar average volume
    "ma5", "ma7", "ma20", "ma25", "ma30", "ma60", "ma99", "ma120",  # moving averages
    "ma_align",           # "정배열" | "역배열" | "혼조"  (uptrend / downtrend / mixed)
    "macd",               # MACD line (EMA12 - EMA26)
    "bb_pct",             # %B within Bollinger Bands (0=lower, 1=upper)
    "bb_width",           # Bollinger band width / mid
    "atr",                # ATR(14)
    "atr_pct",            # ATR / close (%)
    "dist_from_high20",   # % distance from 20-bar high (negative = below)
    "dist_from_low20",    # % distance from 20-bar low (positive = above)
]

# Imports the generated code may use (NO httpx — it does not fetch data anymore).
ALLOWED_IMPORTS = {
    "json",
    "math",
    "statistics",
    "datetime",
    "decimal",
    "typing",
    "numpy",
    "pandas",
}

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
    "httpx",
    "requests",
}

# Inputs the verifier feeds to decide() to confirm the contract holds.
SAMPLE_FEATURES = {
    "close": 91_383_000.0,
    "rsi14": 32.5,
    "vol_ratio": 1.7,
    "ma5": 91_200_000.0,
    "ma7": 91_100_000.0,
    "ma20": 90_800_000.0,
    "ma25": 90_900_000.0,
    "ma30": 90_950_000.0,
    "ma60": 91_050_000.0,
    "ma99": 91_400_000.0,
    "ma120": 91_500_000.0,
    "ma_align": "정배열",
    "macd": 450_000.0,
    "bb_pct": 0.65,
    "bb_width": 0.042,
    "atr": 520_000.0,
    "atr_pct": 0.57,
    "dist_from_high20": -2.1,
    "dist_from_low20": 8.5,
}
# All-None features: decide() must return a valid HOLD-able decision, never raise.
NULL_FEATURES = {key: None for key in FEATURE_KEYS}
SAMPLE_POSITION = {"in_position": False, "entry_price": None, "size_ratio": 0.0}

_FEATURE_DOC = "\n".join(
    f"   - {key}" for key in FEATURE_KEYS
)

SYSTEM_PROMPT = f"""You are a senior quant developer. You write ONE pure Python function that decides a single crypto trade from pre-computed indicators.

HARD REQUIREMENTS — the function is rejected automatically if any are violated:
1. Define exactly this function (signature must match):
   {ENTRYPOINT_SIGNATURE}
2. `features` is a flat dict with these keys (values are floats unless noted):
{_FEATURE_DOC}
   `ma_align` is a string: "정배열" (uptrend), "역배열" (downtrend), or "혼조" (mixed).
3. `position` is a dict {{"in_position": bool, "entry_price": float|None, "size_ratio": float}} or None.
   Treat None / missing as a flat (no) position.
4. Return a dict EXACTLY shaped as:
   {{
     "action": "BUY" | "SELL" | "HOLD",
     "size_ratio": float,   # 0.0..1.0 ; use 0.0 for HOLD
     "reason": str,         # short human-readable rationale (Korean is fine)
     "indicators": {{ ... }}  # optional: the values you keyed off
   }}
   BUY = enter/add, SELL = exit, HOLD = do nothing.
5. NULL-SAFE: if any feature you need is missing or None, DO NOT raise — return HOLD.
   The function is called in real time and must never crash on partial data.
6. PURE: no network, no file/IO, no printing, no top-level side effects. All logic lives
   inside `{ENTRYPOINT_NAME}`. Do NOT fetch data — the backend supplies `features`.
7. ONLY import from this allowlist: {", ".join(sorted(ALLOWED_IMPORTS))}.
   NEVER import or use: {", ".join(sorted(FORBIDDEN_NAMES))}.

OUTPUT FORMAT:
Return ONLY the Python source for the function inside a single ```python fenced code block. No prose.
"""


def build_user_prompt(prompt: str) -> str:
    """Wrap the user's natural-language strategy request."""
    return (
        f"Write the `decide` function for this strategy:\n\n{prompt}\n\n"
        "It will be verified by calling it with a full feature dict and with an "
        "all-None feature dict; both must return a valid BUY/SELL/HOLD decision "
        "without raising."
    )


def build_retry_prompt(errors: list[str], stage: str) -> str:
    """Feedback message appended after a failed verification attempt."""
    joined = "\n".join(f"- {e}" for e in errors) or "- (no detail captured)"
    return (
        f"The previous function FAILED verification at the '{stage}' stage:\n{joined}\n\n"
        "Fix these problems and return the full corrected function again as a single "
        "```python fenced code block. Keep the same signature and contract, and make "
        "sure it returns HOLD (never raises) when features are missing/None."
    )
