export type Scenario = {
  id: string;
  market: string;
  timeframe: string;
  description: string;
  features_snapshot: Record<string, unknown>;
  chart_data: Array<Record<string, unknown>>;
};

export type ScenarioListResponse = {
  items: Scenario[];
};

export type Decision =
  | "buy"
  | "sell"
  | "hold"
  | "wait"
  | "add_position"
  | "take_profit"
  | "stop_loss"
  | "uncertain";

export type UserResponsePayload = {
  scenario_id: string;
  decision: Decision;
  natural_reason: string;
  confidence: number;
  preferred_action: string;
};

export type UserResponseWriteResponse = {
  response_id: string;
  response_count: number;
  can_generate_twin: boolean;
};

export type UserResponseListResponse = {
  response_count: number;
  can_generate_twin: boolean;
  items: Array<{
    id: string;
    scenario_id: string;
    decision: Decision;
    natural_reason: string;
    confidence: number;
    preferred_action: string;
  }>;
};

export type TwinContext = {
  context_id: string | null;
  version: number | null;
  style_summary: string | null;
  important_signals: string[];
  avoid_conditions: string[];
  uncertainty: string[];
};
