"""Single source of truth for the contract that LLM-generated trading code must satisfy.

The harness asks Claude for ONE self-contained Python script. The script takes no
arguments: when executed it fetches whatever Upbit data it needs over httpx, evaluates
the strategy, and prints exactly one decision token — "buy" or "reject" — to stdout.
The market/asset and timeframe are chosen freely by the model from the strategy text.

Both the verifier and the prompt are derived from the constants here so they never drift.
"""

# The only two outputs the script may print.
DECISIONS = ("buy", "reject")

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

SYSTEM_PROMPT = f"""You are a senior quant developer. You write a SINGLE self-contained Python script that decides ONE crypto trade based on live Upbit market data.

HARD REQUIREMENTS — the script is rejected automatically if any are violated:
1. The script takes NO arguments. When run (`python script.py`) it does all its work and then prints EXACTLY ONE line to stdout: either `buy` or `reject` — and nothing else on that final line.
   - `buy`  = enter the position now.
   - `reject` = do not enter.
2. Choose the market/asset and timeframe YOURSELF based on the strategy described. Fetch the candle/ticker data you need directly from Upbit's public REST API using `httpx`.
   - Endpoint example: GET https://api.upbit.com/v1/candles/minutes/15?market=KRW-BTC&count=100
   - Upbit candle fields: opening_price, high_price, low_price, trade_price (close), candle_acc_trade_volume.
3. ONLY import from this allowlist: {", ".join(sorted(ALLOWED_IMPORTS))}.
   NEVER import or call: {", ".join(sorted(FORBIDDEN_NAMES))}.
4. Handle errors defensively: set a short httpx timeout, and if data is insufficient or any error occurs, print `reject`.
5. The decision must be printed when the script runs as the main program (use an `if __name__ == "__main__":` block, or print at the end). Do not print anything other than the final `buy`/`reject` token.

OUTPUT FORMAT:
Return ONLY the Python source code inside a single ```python fenced code block. No prose before or after.
"""


def build_user_prompt(prompt: str) -> str:
    """Wrap the user's natural-language strategy request."""
    return (
        f"Write the trading script for this strategy request:\n\n{prompt}\n\n"
        "It will be verified by running it with no arguments and reading the final "
        "line of stdout, which must be exactly `buy` or `reject`."
    )


def build_retry_prompt(errors: list[str], stage: str) -> str:
    """Feedback message appended after a failed verification attempt."""
    joined = "\n".join(f"- {e}" for e in errors) or "- (no detail captured)"
    return (
        f"The previous script FAILED verification at the '{stage}' stage:\n{joined}\n\n"
        "Fix these problems and return the full corrected script again as a single "
        "```python fenced code block. It must still run with no arguments and print "
        "exactly `buy` or `reject`."
    )
