async function getBackendStatus(): Promise<"online" | "offline"> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return "offline";
    }
    const body = (await response.json()) as { status?: string };
    return body.status === "ok" ? "online" : "offline";
  } catch {
    return "offline";
  }
}

export default async function Home() {
  const status = await getBackendStatus();

  return (
    <main>
      <section className="shell">
        <p className="status">
          <span className={`dot ${status}`} aria-hidden="true" />
          Backend health: {status}
        </p>
        <h1>CoinTwin MVP</h1>
        <p>
          Session 0 initializes the FastAPI backend, backend worker, PostgreSQL
          compose service, and Next.js frontend shell.
        </p>
      </section>
    </main>
  );
}
