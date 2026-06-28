import type {
  ScenarioListResponse,
  TwinContext,
  UserResponseListResponse,
  UserResponsePayload,
  UserResponseWriteResponse,
} from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchScenarios(): Promise<ScenarioListResponse> {
  const response = await fetch(`${apiBaseUrl}/api/scenarios`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to load scenarios");
  }
  return response.json() as Promise<ScenarioListResponse>;
}

export async function fetchMyResponses(): Promise<UserResponseListResponse> {
  const response = await fetch(`${apiBaseUrl}/api/responses/me`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to load responses");
  }
  return response.json() as Promise<UserResponseListResponse>;
}

export async function submitUserResponse(
  payload: UserResponsePayload,
): Promise<UserResponseWriteResponse> {
  const response = await fetch(`${apiBaseUrl}/api/responses`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Failed to save response");
  }
  return response.json() as Promise<UserResponseWriteResponse>;
}

export async function fetchLatestTwinContext(): Promise<TwinContext> {
  const response = await fetch(`${apiBaseUrl}/api/twin-contexts/latest`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to load twin context");
  }
  return response.json() as Promise<TwinContext>;
}

export async function generateTwinContext(): Promise<TwinContext> {
  const response = await fetch(`${apiBaseUrl}/api/twin-contexts/generate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to generate twin context");
  }
  return response.json() as Promise<TwinContext>;
}
