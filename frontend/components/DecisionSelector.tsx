"use client";

import type { Decision } from "../lib/types";

const decisions: Array<{ value: Decision; label: string }> = [
  { value: "buy", label: "매수" },
  { value: "sell", label: "매도" },
  { value: "hold", label: "보유" },
  { value: "wait", label: "관망" },
  { value: "add_position", label: "추가 진입" },
  { value: "take_profit", label: "익절" },
  { value: "stop_loss", label: "손절" },
  { value: "uncertain", label: "불확실" },
];

type DecisionSelectorProps = {
  value: Decision;
  onChange: (value: Decision) => void;
};

export function DecisionSelector({ value, onChange }: DecisionSelectorProps) {
  return (
    <label className="field">
      <span>판단</span>
      <select value={value} onChange={(event) => onChange(event.target.value as Decision)}>
        {decisions.map((decision) => (
          <option key={decision.value} value={decision.value}>
            {decision.label}
          </option>
        ))}
      </select>
    </label>
  );
}
