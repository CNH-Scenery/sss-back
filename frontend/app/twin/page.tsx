"use client";

import { useEffect, useState } from "react";

import { fetchLatestTwinContext, generateTwinContext } from "../../lib/api";
import type { TwinContext } from "../../lib/types";

type TwinStatus = "loading" | "ready" | "empty" | "generating" | "error";

export default function TwinPage() {
  const [context, setContext] = useState<TwinContext | null>(null);
  const [status, setStatus] = useState<TwinStatus>("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function loadLatest() {
      try {
        const latest = await fetchLatestTwinContext();
        setContext(latest);
        setStatus("ready");
        setMessage("");
      } catch {
        setStatus("empty");
        setMessage("저장된 TwinContext가 없습니다.");
      }
    }

    void loadLatest();
  }, []);

  async function handleGenerate() {
    setStatus("generating");
    setMessage("");
    try {
      const generated = await generateTwinContext();
      setContext(generated);
      setStatus("ready");
      setMessage("TwinContext가 생성되었습니다.");
    } catch {
      setStatus("error");
      setMessage("응답 10개를 저장한 뒤 다시 생성하세요.");
    }
  }

  return (
    <main>
      <section className="shell twin-shell">
        <p className="status">Twin status: {status}</p>
        <div className="twin-header">
          <div>
            <h1>TwinContext</h1>
            <p>Version {context?.version ?? "-"}</p>
          </div>
          <button type="button" onClick={handleGenerate} disabled={status === "generating"}>
            생성
          </button>
        </div>

        {message ? <p className="save-status">{message}</p> : null}

        {context ? (
          <div className="twin-summary">
            <section>
              <h2>style_summary</h2>
              <p>{context.style_summary}</p>
            </section>

            <TwinList title="important_signals" items={context.important_signals} />
            <TwinList title="avoid_conditions" items={context.avoid_conditions} />
            <TwinList title="uncertainty" items={context.uncertainty} />
          </div>
        ) : (
          <p className="empty-state">생성된 성향 요약이 없습니다.</p>
        )}
      </section>
    </main>
  );
}

function TwinList({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h2>{title}</h2>
      <ul className="twin-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
