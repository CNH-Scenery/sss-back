from typing import Any


class PromptBuilder:
    @staticmethod
    def build_twin_context_prompt(responses: list[dict[str, Any]]) -> str:
        lines = [
            "You are generating a CoinTwin user decision profile.",
            f"Response count: {len(responses)}",
            "Summarize style, important signals, avoid conditions, and uncertainty.",
        ]
        for index, response in enumerate(responses, start=1):
            scenario = response["scenario"]
            lines.extend(
                [
                    f"[{index}] {scenario['market']} {scenario['timeframe']}",
                    f"Scenario: {scenario['description']}",
                    f"Features: {scenario['features_snapshot']}",
                    f"Decision: {response['decision']}",
                    f"Reason: {response['natural_reason']}",
                    f"Confidence: {response['confidence']}",
                    f"Preferred action: {response['preferred_action']}",
                ]
            )
        return "\n".join(lines)
