from uuid import UUID

from sqlmodel import Session, select

from app.models import Scenario

STATIC_SCENARIOS = [
    {
        "id": UUID("00000000-0000-4000-8000-000000000001"),
        "market": "KRW-BTC",
        "timeframe": "15m",
        "description": "거래량이 증가하며 직전 고점을 테스트하는 구간",
        "features_snapshot": {"volume_ratio_n": 1.7, "recent_high_breakout": 0.8},
        "chart_data": [{"t": 1, "close": 100}, {"t": 2, "close": 103}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000002"),
        "market": "KRW-BTC",
        "timeframe": "15m",
        "description": "급등 이후 윗꼬리가 반복되는 부담스러운 구간",
        "features_snapshot": {"upper_wick_ratio": 0.52, "rapid_price_rise": 0.9},
        "chart_data": [{"t": 1, "close": 100}, {"t": 2, "close": 112}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000003"),
        "market": "KRW-ETH",
        "timeframe": "15m",
        "description": "돌파 후 눌림이 나오며 거래량이 줄어든 구간",
        "features_snapshot": {"pullback_after_breakout": 0.7, "volume_fading": 0.4},
        "chart_data": [{"t": 1, "close": 200}, {"t": 2, "close": 196}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000004"),
        "market": "KRW-ETH",
        "timeframe": "15m",
        "description": "지지선 근처에서 하락이 멈추고 반등을 시도하는 구간",
        "features_snapshot": {"lower_wick_ratio": 0.44, "drawdown_from_recent_high": 0.08},
        "chart_data": [{"t": 1, "close": 200}, {"t": 2, "close": 202}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000005"),
        "market": "KRW-XRP",
        "timeframe": "15m",
        "description": "거래량 없이 완만하게 상승하는 추세 지속 구간",
        "features_snapshot": {"moving_average_slope": 0.3, "volume_ratio_n": 0.8},
        "chart_data": [{"t": 1, "close": 50}, {"t": 2, "close": 51}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000006"),
        "market": "KRW-SOL",
        "timeframe": "15m",
        "description": "RSI가 과열권에 진입했지만 고점 돌파가 유지되는 구간",
        "features_snapshot": {"rsi_14": 74, "recent_high_breakout": 0.9},
        "chart_data": [{"t": 1, "close": 80}, {"t": 2, "close": 85}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000007"),
        "market": "KRW-DOGE",
        "timeframe": "15m",
        "description": "급락 이후 변동성이 커지고 방향성이 불명확한 구간",
        "features_snapshot": {"volatility_n": 0.9, "recent_low_breakdown": 0.6},
        "chart_data": [{"t": 1, "close": 20}, {"t": 2, "close": 18}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000008"),
        "market": "KRW-BTC",
        "timeframe": "15m",
        "description": "상승 후 거래량이 줄며 횡보하는 관망 구간",
        "features_snapshot": {"volume_fading": 0.7, "price_return_n": 0.01},
        "chart_data": [{"t": 1, "close": 105}, {"t": 2, "close": 105}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000009"),
        "market": "KRW-ETH",
        "timeframe": "15m",
        "description": "지지선 이탈 직후 반등 없이 약세가 이어지는 구간",
        "features_snapshot": {"support_break": 0.8, "recent_low_breakdown": 0.9},
        "chart_data": [{"t": 1, "close": 190}, {"t": 2, "close": 184}],
    },
    {
        "id": UUID("00000000-0000-4000-8000-000000000010"),
        "market": "KRW-SOL",
        "timeframe": "15m",
        "description": "거래량이 동반된 반등이 나오지만 직전 저항에 가까운 구간",
        "features_snapshot": {"volume_ratio_n": 1.4, "drawdown_from_recent_high": 0.03},
        "chart_data": [{"t": 1, "close": 77}, {"t": 2, "close": 81}],
    },
]


def seed_static_scenarios(session: Session) -> None:
    existing_ids = set(session.exec(select(Scenario.id)).all())
    added = False
    for item in STATIC_SCENARIOS:
        if item["id"] in existing_ids:
            continue
        session.add(Scenario(**item))
        added = True
    if added:
        session.commit()
