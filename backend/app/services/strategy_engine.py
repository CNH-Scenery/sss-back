"""Runs a generated `decide` function in an isolated subprocess.

One trusted runner imports the LLM `decide()` once and then either:
  - evaluate: calls it on a list of (features, position) inputs -> decisions
              (used by the verifier's probes and by single live decisions), or
  - backtest: drives a standard long-only simulation loop, calling decide() per bar
              with the evolving position, and returns trades + metrics + equity.

The simulation logic lives in the trusted runner (not the LLM code), so the backtest
format stays consistent regardless of what the model generated.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

RUNTIME_TIMEOUT_SECONDS = 30
CPU_LIMIT_SECONDS = 25
MARKER = "__ENGINE__"

_RUNNER = r'''
import sys, json

strategy_path, payload_path = sys.argv[1], sys.argv[2]
with open(strategy_path, encoding="utf-8") as fh:
    src = fh.read()
with open(payload_path, encoding="utf-8") as fh:
    payload = json.load(fh)

ns = {}
try:
    exec(compile(src, strategy_path, "exec"), ns)
except Exception as exc:
    print("__ENGINE__" + json.dumps({"engine_error": "exec failed: %s: %s" % (type(exc).__name__, exc)}))
    sys.exit(0)

decide = ns.get("decide")
if not callable(decide):
    print("__ENGINE__" + json.dumps({"engine_error": "decide() is not defined"}))
    sys.exit(0)

def _call(features, position):
    d = decide(features or {}, position)
    if not isinstance(d, dict):
        raise ValueError("decide must return a dict, got %r" % type(d).__name__)
    return d

mode = payload.get("mode")

if mode == "evaluate":
    results = []
    for call in payload.get("calls", []):
        try:
            results.append({"ok": True, "decision": _call(call.get("features"), call.get("position"))})
        except Exception as exc:
            results.append({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)})
    print("__ENGINE__" + json.dumps({"results": results}, default=str))
    sys.exit(0)

if mode == "backtest":
    keys = payload["feature_keys"]
    rows = payload["rows"]
    cash = float(payload["initial_cash"])
    fee = float(payload.get("fee_rate", 0.0005))
    start_cash = cash
    units = 0.0
    position = {"in_position": False, "entry_price": None, "size_ratio": 0.0}
    entry_price = None
    entry_time = None
    trades = []
    markers = []
    equity = []
    closes = [float(r["close"]) for r in rows]

    for i, row in enumerate(rows):
        price = float(row["close"])
        feats = {k: row.get(k) for k in keys}
        try:
            d = _call(feats, position)
            action = str(d.get("action", "HOLD")).strip().upper()
            size = float(d.get("size_ratio") or 0.0)
            reason = str(d.get("reason", ""))
        except Exception as exc:
            action, size, reason = "HOLD", 0.0, "decide error: %s" % exc
        if action not in ("BUY", "SELL", "HOLD"):
            action = "HOLD"
        size = max(0.0, min(1.0, size))

        if action == "BUY" and not position["in_position"]:
            spend = cash * (size if size > 0 else 1.0)
            if spend > 0:
                units = (spend * (1 - fee)) / price
                cash -= spend
                entry_price, entry_time = price, row.get("candle_time")
                position = {"in_position": True, "entry_price": price, "size_ratio": size if size > 0 else 1.0}
                markers.append({"i": i, "type": "BUY"})
        elif action == "SELL" and position["in_position"]:
            proceeds = units * price * (1 - fee)
            cash += proceeds
            ret_pct = (price / entry_price - 1) * 100 if entry_price else 0.0
            trades.append({
                "side": "long",
                "entry_time": entry_time, "entry_price": entry_price,
                "exit_time": row.get("candle_time"), "exit_price": price,
                "return_pct": ret_pct, "reason": reason,
            })
            units = 0.0
            entry_price, entry_time = None, None
            position = {"in_position": False, "entry_price": None, "size_ratio": 0.0}
            markers.append({"i": i, "type": "SELL"})

        equity.append(cash + units * price)

    # Close any open position at the last bar so metrics are realized.
    if position["in_position"] and rows:
        price = float(rows[-1]["close"])
        cash += units * price * (1 - fee)
        ret_pct = (price / entry_price - 1) * 100 if entry_price else 0.0
        trades.append({
            "side": "long",
            "entry_time": entry_time, "entry_price": entry_price,
            "exit_time": rows[-1].get("candle_time"), "exit_price": price,
            "return_pct": ret_pct, "reason": "백테스트 종료 청산",
        })
        units = 0.0
        if equity:
            equity[-1] = cash

    final = equity[-1] if equity else start_cash
    total_return = (final / start_cash - 1) * 100 if start_cash else 0.0
    bh_return = (closes[-1] / closes[0] - 1) * 100 if len(closes) >= 2 and closes[0] else 0.0
    wins = sum(1 for t in trades if t["return_pct"] > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0.0
    peak = -1e18
    mdd = 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            mdd = min(mdd, (e / peak - 1) * 100)

    base = start_cash if start_cash else 1.0
    eq_norm = [e / base for e in equity]
    first_close = closes[0] if closes else 0.0
    bh_norm = [(c / first_close) if first_close else 1.0 for c in closes]
    candles_out = [{
        "t": r.get("candle_time"),
        "o": float(r.get("open") or r["close"]),
        "h": float(r.get("high") or r["close"]),
        "l": float(r.get("low") or r["close"]),
        "c": float(r["close"]),
    } for r in rows]

    print("__ENGINE__" + json.dumps({"backtest": {
        "metrics": {
            "totalReturn": total_return, "bhReturn": bh_return, "winRate": win_rate,
            "trades": len(trades), "mdd": mdd, "vsBH": total_return - bh_return,
        },
        "eq": eq_norm, "bh": bh_norm, "candles": candles_out,
        "markers": markers, "trades": trades,
    }}, default=str))
    sys.exit(0)

print("__ENGINE__" + json.dumps({"engine_error": "unknown mode: %r" % mode}))
'''


def _limit_resources() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    except Exception:  # noqa: BLE001
        pass


def _run(code: str, payload: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        strategy_path = Path(tmp) / "strategy_mod.py"
        payload_path = Path(tmp) / "payload.json"
        strategy_path.write_text(code, encoding="utf-8")
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        kwargs: dict[str, Any] = {}
        if os.name != "nt":
            kwargs["preexec_fn"] = _limit_resources
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", _RUNNER, str(strategy_path), str(payload_path)],
                capture_output=True,
                text=True,
                timeout=RUNTIME_TIMEOUT_SECONDS,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            return {"engine_error": f"execution exceeded {RUNTIME_TIMEOUT_SECONDS}s timeout"}

        if proc.returncode != 0:
            return {"engine_error": (proc.stderr or proc.stdout or "non-zero exit")[:2000]}

        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(MARKER)), None)
        if line is None:
            return {"engine_error": "no engine output", "stdout": proc.stdout[:2000]}
        try:
            return json.loads(line[len(MARKER):])
        except json.JSONDecodeError as exc:
            return {"engine_error": f"bad engine output: {exc}"}


def evaluate(code: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Call decide() on each {features, position} input. Returns {results:[...]} or {engine_error}."""
    return _run(code, {"mode": "evaluate", "calls": calls})


def backtest(
    code: str,
    feature_rows: list[dict[str, Any]],
    feature_keys: list[str],
    initial_cash: float,
    fee_rate: float = 0.0005,
) -> dict[str, Any]:
    """Drive the long-only simulation loop over feature_rows. Returns {backtest:{...}} or {engine_error}."""
    return _run(
        code,
        {
            "mode": "backtest",
            "feature_keys": feature_keys,
            "rows": feature_rows,
            "initial_cash": initial_cash,
            "fee_rate": fee_rate,
        },
    )
