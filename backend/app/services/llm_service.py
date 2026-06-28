from collections import Counter
from statistics import mean
from typing import Any

from app.services.prompt_builder import PromptBuilder

ENTRY_DECISIONS = {"buy", "add_position"}
EXIT_DECISIONS = {"sell", "take_profit", "stop_loss"}
WAIT_DECISIONS = {"hold", "wait", "uncertain"}

SIGNAL_LABELS = {
    "volume_ratio_n": "거래량 증가",
    "recent_high_breakout": "직전 고점 돌파",
    "upper_wick_ratio": "윗꼬리 부담",
    "rapid_price_rise": "단기 급등",
    "pullback_after_breakout": "돌파 후 눌림",
    "volume_fading": "거래량 감소",
    "lower_wick_ratio": "아래꼬리 반등",
    "drawdown_from_recent_high": "고점 대비 조정",
    "moving_average_slope": "이동평균 기울기",
    "rsi_14": "RSI 과열",
    "volatility_n": "변동성 확대",
    "recent_low_breakdown": "직전 저점 이탈",
    "price_return_n": "단기 수익률",
    "support_break": "지지선 이탈",
}


class LLMService:
    def analyze_user_responses(self, responses: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = PromptBuilder.build_twin_context_prompt(responses)
        decision_counts = Counter(str(response["decision"]) for response in responses)
        confidence_values = [float(response["confidence"]) for response in responses]
        average_confidence = round(mean(confidence_values), 3)

        entry_count = sum(decision_counts[decision] for decision in ENTRY_DECISIONS)
        exit_count = sum(decision_counts[decision] for decision in EXIT_DECISIONS)
        wait_count = sum(decision_counts[decision] for decision in WAIT_DECISIONS)

        feature_counts = self._feature_counts(responses)
        avoid_feature_counts = self._avoid_feature_counts(responses)

        return {
            "style_summary": self._style_summary(entry_count, exit_count, wait_count, average_confidence),
            "important_signals": self._important_signals(feature_counts),
            "avoid_conditions": self._avoid_conditions(avoid_feature_counts, responses),
            "uncertainty": self._uncertainty(decision_counts, average_confidence, len(responses)),
            "decision_profile": {
                **dict(decision_counts),
                "entry_bias_count": entry_count,
                "exit_bias_count": exit_count,
                "wait_bias_count": wait_count,
            },
            "confidence_profile": {
                "average": average_confidence,
                "minimum": round(min(confidence_values), 3),
                "maximum": round(max(confidence_values), 3),
                "band": self._confidence_band(average_confidence),
                "prompt_char_count": float(len(prompt)),
            },
        }

    def _feature_counts(self, responses: list[dict[str, Any]]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for response in responses:
            weight = 2 if response["decision"] in ENTRY_DECISIONS else 1
            for feature in response["scenario"]["features_snapshot"]:
                counts[feature] += weight
        return counts

    def _avoid_feature_counts(self, responses: list[dict[str, Any]]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for response in responses:
            if response["decision"] not in EXIT_DECISIONS | WAIT_DECISIONS:
                continue
            for feature in response["scenario"]["features_snapshot"]:
                counts[feature] += 1
        return counts

    def _style_summary(
        self,
        entry_count: int,
        exit_count: int,
        wait_count: int,
        average_confidence: float,
    ) -> str:
        confidence_text = self._confidence_band(average_confidence)
        if entry_count >= exit_count and entry_count >= wait_count:
            return f"거래량과 돌파 신호를 확인한 뒤 제한적으로 진입하는 {confidence_text} 성향입니다."
        if exit_count >= entry_count and exit_count >= wait_count:
            return f"위험 신호가 보이면 익절 또는 손절을 빠르게 고려하는 {confidence_text} 방어형 성향입니다."
        return f"불확실한 구간에서 추가 확인을 우선하는 {confidence_text} 관망형 성향입니다."

    def _important_signals(self, feature_counts: Counter[str]) -> list[str]:
        signals = [SIGNAL_LABELS.get(feature, feature) for feature, _ in feature_counts.most_common(5)]
        return self._unique_or_default(signals, "거래량과 가격 위치를 함께 확인하는 패턴")

    def _avoid_conditions(
        self,
        avoid_feature_counts: Counter[str],
        responses: list[dict[str, Any]],
    ) -> list[str]:
        conditions = [
            SIGNAL_LABELS.get(feature, feature)
            for feature, _ in avoid_feature_counts.most_common(4)
        ]
        reason_text = " ".join(str(response["natural_reason"]) for response in responses)
        if "윗꼬리" in reason_text:
            conditions.append("윗꼬리가 반복되는 구간")
        if "불확실" in reason_text:
            conditions.append("방향성이 불명확한 구간")
        if "지지" in reason_text:
            conditions.append("지지선 이탈 직후 구간")
        return self._unique_or_default(conditions, "확신도가 낮은 변동성 확대 구간")

    def _uncertainty(
        self,
        decision_counts: Counter[str],
        average_confidence: float,
        response_count: int,
    ) -> list[str]:
        items = [f"응답 {response_count}개는 TwinContext 생성을 위한 최소 표본입니다."]
        if average_confidence < 0.65:
            items.append("평균 확신도가 낮아 동일 조건에서 판단이 흔들릴 수 있습니다.")
        if decision_counts["uncertain"] > 0:
            items.append("불확실 판단이 포함되어 진입 기준을 더 좁게 검증해야 합니다.")
        if len(decision_counts) >= 5:
            items.append("판단 유형이 넓게 분산되어 우선순위가 약한 신호가 섞여 있습니다.")
        return self._unique_or_default(items, "추가 응답과 피드백으로 성향을 보정해야 합니다.")

    def _confidence_band(self, average_confidence: float) -> str:
        if average_confidence >= 0.75:
            return "높은 확신도의"
        if average_confidence >= 0.6:
            return "중간 확신도의"
        return "낮은 확신도의"

    def _unique_or_default(self, items: list[str], default: str) -> list[str]:
        unique_items = list(dict.fromkeys(item for item in items if item))
        return unique_items or [default]
