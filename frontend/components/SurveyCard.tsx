"use client";

import { useState } from "react";

import { submitUserResponse } from "../lib/api";
import type { Decision, Scenario } from "../lib/types";
import { ConfidenceSlider } from "./ConfidenceSlider";
import { DecisionSelector } from "./DecisionSelector";

type SurveyCardProps = {
  scenario: Scenario;
  onSaved: (responseCount: number, can_generate_twin: boolean) => void;
};

export function SurveyCard({ scenario, onSaved }: SurveyCardProps) {
  const [decision, setDecision] = useState<Decision>("wait");
  const [naturalReason, setNaturalReason] = useState("");
  const [confidence, setConfidence] = useState(0.6);
  const [preferredAction, setPreferredAction] = useState("wait_for_confirmation");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  async function handleSubmit() {
    setStatus("saving");
    try {
      const result = await submitUserResponse({
        scenario_id: scenario.id,
        decision,
        natural_reason: naturalReason,
        confidence,
        preferred_action: preferredAction,
      });
      onSaved(result.response_count, result.can_generate_twin);
      setStatus("saved");
    } catch {
      setStatus("error");
    }
  }

  return (
    <article className="survey-card">
      <div>
        <p className="market">
          {scenario.market} · {scenario.timeframe}
        </p>
        <h2>{scenario.description}</h2>
        <pre>{JSON.stringify(scenario.chart_data, null, 2)}</pre>
      </div>

      <DecisionSelector value={decision} onChange={setDecision} />

      <label className="field">
        <span>이유</span>
        <textarea
          value={naturalReason}
          onChange={(event) => setNaturalReason(event.target.value)}
          placeholder="왜 그렇게 판단했는지 적어주세요."
          rows={4}
        />
      </label>

      <ConfidenceSlider value={confidence} onChange={setConfidence} />

      <label className="field">
        <span>선호 행동</span>
        <input
          value={preferredAction}
          onChange={(event) => setPreferredAction(event.target.value)}
        />
      </label>

      <button type="button" onClick={handleSubmit} disabled={status === "saving"}>
        저장
      </button>
      <p className="save-status">{status}</p>
    </article>
  );
}
