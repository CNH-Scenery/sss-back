"use client";

type ConfidenceSliderProps = {
  value: number;
  onChange: (value: number) => void;
};

export function ConfidenceSlider({ value, onChange }: ConfidenceSliderProps) {
  return (
    <label className="field">
      <span>확신도 {Math.round(value * 100)}%</span>
      <input
        min="0"
        max="1"
        step="0.05"
        type="range"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
