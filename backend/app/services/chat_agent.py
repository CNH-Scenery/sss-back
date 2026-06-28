"""Natural-language Upbit market-data assistant (read-only).

Runs a Claude tool-use loop: the model answers user questions by calling
read-only Upbit tools (price, orderbook, candles, market list). It cannot place
orders, read balances, or move funds — this app is analysis/look-up only, in
line with its read-only design. Inspired by Upbit Agent Skills, but implemented
natively as Claude tools rather than the upbit CLI.
"""
import json
from collections.abc import Iterator
from typing import Any

from app.services.anthropic_client import fixture_enabled, get_model
from app.services.upbit_client import UpbitClient

MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """당신은 업비트(Upbit) 암호화폐 거래소의 읽기 전용 시세 도우미입니다.
사용자의 자연어 질문에 답하기 위해 제공된 도구로 실시간 현재가·호가·캔들·마켓 목록을 조회할 수 있습니다.

규칙:
- 답변은 한국어로, 간결하고 정확하게 한다.
- 가격은 원(KRW) 단위로 천 단위 구분 기호와 함께 표기한다 (예: 92,418,000원).
- 마켓 코드는 'KRW-BTC' 형식이다. 사용자가 '비트코인'이라고 하면 'KRW-BTC', '이더리움'이면 'KRW-ETH'로 해석한다.
- 시세·호가·캔들 관련 질문에는 추측하지 말고 반드시 도구로 최신 값을 조회한 뒤 답한다.
- 당신은 주문(매수/매도) 실행, 잔고 조회, 입출금을 할 수 없다. 이 앱은 분석·조회 전용이며 주문은 사용자가 직접 한다. 그런 요청을 받으면 정중히 거절하고, 대신 시세·지표 분석을 돕는다.
- 투자 권유나 단정적 수익 보장은 하지 않는다. 정보 제공과 분석에 집중한다.
"""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_krw_markets",
        "description": "업비트에서 거래 가능한 KRW 마켓(원화 마켓) 코드 목록을 반환한다. 어떤 코인이 상장돼 있는지 확인할 때 사용.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_price",
        "description": "하나 이상의 마켓에 대한 현재가와 24시간 변동률·고가·저가·거래량을 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "markets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "마켓 코드 배열, 예: ['KRW-BTC', 'KRW-ETH']",
                }
            },
            "required": ["markets"],
        },
    },
    {
        "name": "get_orderbook",
        "description": "한 마켓의 매수/매도 호가(상위 5단계)를 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "마켓 코드, 예: 'KRW-BTC'"}
            },
            "required": ["market"],
        },
    },
    {
        "name": "get_candles",
        "description": "한 마켓의 캔들(봉) 데이터를 최신순으로 조회한다. 추세·이동평균·변동성 분석에 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "마켓 코드, 예: 'KRW-BTC'"},
                "timeframe": {
                    "type": "string",
                    "enum": ["15m", "60m", "1d"],
                    "description": "봉 단위: 15분/60분/일봉",
                },
                "count": {
                    "type": "integer",
                    "description": "가져올 봉 개수 (1~200, 기본 30)",
                },
            },
            "required": ["market", "timeframe"],
        },
    },
]


class ChatAgent:
    def __init__(self, client: Any | None = None, upbit: UpbitClient | None = None) -> None:
        self._upbit = upbit or UpbitClient()
        self.model = get_model()
        self._fixture = fixture_enabled()
        self._client = client
        if self._client is None and not self._fixture:
            import anthropic

            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    @property
    def model_name(self) -> str:
        return "fixture" if self._fixture else self.model

    def _run_tool(self, name: str, tool_input: dict[str, Any]) -> Any:
        if name == "list_krw_markets":
            return {"markets": self._upbit.list_krw_markets()}
        if name == "get_price":
            return {"tickers": self._upbit.get_ticker(list(tool_input.get("markets", [])))}
        if name == "get_orderbook":
            return self._upbit.get_orderbook(str(tool_input["market"]))
        if name == "get_candles":
            market = str(tool_input["market"])
            timeframe = str(tool_input.get("timeframe", "1d"))
            count = max(1, min(int(tool_input.get("count", 30)), 200))
            if timeframe == "1d":
                candles = self._upbit.list_daily_candles(market, count)
            else:
                unit = 15 if timeframe == "15m" else 60
                candles = self._upbit.list_minute_candles(market, unit, count)
            return {"candles": candles}
        raise ValueError(f"unknown tool: {name}")

    def stream(self, messages: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Yields events: start | text | tool_use | tool_result | done | error."""
        yield {"event": "start", "model_name": self.model_name}

        if self._fixture:
            yield {
                "event": "text",
                "delta": "데모(fixture) 모드입니다. 실시간 챗봇은 백엔드에 유효한 ANTHROPIC_API_KEY가 필요합니다.",
            }
            yield {"event": "done"}
            return

        convo: list[dict[str, Any]] = list(messages)
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                with self._client.messages.stream(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=convo,
                ) as stream:
                    for text in stream.text_stream:
                        yield {"event": "text", "delta": text}
                    final = stream.get_final_message()

                convo.append({"role": "assistant", "content": final.content})
                tool_uses = [b for b in final.content if b.type == "tool_use"]
                if not tool_uses:
                    yield {"event": "done"}
                    return

                results: list[dict[str, Any]] = []
                for tu in tool_uses:
                    yield {"event": "tool_use", "name": tu.name, "input": tu.input}
                    try:
                        output = self._run_tool(tu.name, dict(tu.input))
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": json.dumps(output, ensure_ascii=False),
                            }
                        )
                        yield {"event": "tool_result", "name": tu.name, "ok": True}
                    except Exception as exc:  # noqa: BLE001 - report tool failure back to the model
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": f"error: {type(exc).__name__}: {exc}",
                                "is_error": True,
                            }
                        )
                        yield {"event": "tool_result", "name": tu.name, "ok": False, "message": str(exc)}

                convo.append({"role": "user", "content": results})

            # Hit the tool-round cap without a final text answer.
            yield {"event": "done"}
        except Exception as exc:  # noqa: BLE001 - surface to client
            yield {"event": "error", "message": f"{type(exc).__name__}: {exc}"}
            yield {"event": "done"}
