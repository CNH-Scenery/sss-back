"use client";

import { useEffect, useState } from "react";

import { SurveyCard } from "../../components/SurveyCard";
import { fetchMyResponses, fetchScenarios } from "../../lib/api";
import type { Scenario } from "../../lib/types";

export default function SurveyPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [responseCount, setResponseCount] = useState(0);
  const [canGenerateTwin, setCanGenerateTwin] = useState(false);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    async function load() {
      try {
        const [scenarioResult, responseResult] = await Promise.all([
          fetchScenarios(),
          fetchMyResponses(),
        ]);
        setScenarios(scenarioResult.items);
        setResponseCount(responseResult.response_count);
        setCanGenerateTwin(responseResult.can_generate_twin);
        setStatus("ready");
      } catch {
        setStatus("error");
      }
    }

    void load();
  }, []);

  return (
    <main>
      <section className="shell">
        <p className="status">Survey status: {status}</p>
        <h1>판단 수집</h1>
        <p>
          응답 {responseCount}/10 ·{" "}
          {canGenerateTwin ? "트윈 생성 가능" : "트윈 생성을 위해 10개 응답 필요"}
        </p>
        <div className="survey-grid">
          {scenarios.map((scenario) => (
            <SurveyCard
              key={scenario.id}
              scenario={scenario}
              onSaved={(count, can_generate_twin) => {
                setResponseCount(count);
                setCanGenerateTwin(can_generate_twin);
              }}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
