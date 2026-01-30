import React, { useEffect, useMemo, useState } from "react";

export function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch("/api/metrics");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json.metrics ?? json);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const cards = useMemo(() => {
    if (!data) return [];
    const toNum = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : 0;
    };

    const l1Calls = toNum(data.l1_calls_total);
    const l2Calls = toNum(data.l2_calls_total);
    const llmCalls = toNum(data.llm_calls_total);
    const requestsTotal = l1Calls + l2Calls + llmCalls;

    const l1LatencySum = toNum(data.l1_latency_ms_sum);
    const l2LatencySum = toNum(data.l2_latency_ms_sum);
    const llmLatencySum = toNum(data.llm_latency_ms_sum);

    const pct = (n, d) => (d > 0 ? (n / d) * 100 : 0);
    const avg = (sum, n) => (n > 0 ? sum / n : 0);

    return [
      { key: "l1", title: "L1 (Exact Query Match)", pct: pct(l1Calls, requestsTotal), latency: avg(l1LatencySum, l1Calls), calls: l1Calls },
      { key: "l2", title: "L2 (Vector Embedding Match)", pct: pct(l2Calls, requestsTotal), latency: avg(l2LatencySum, l2Calls), calls: l2Calls },
      { key: "llm", title: "LLM", pct: pct(llmCalls, requestsTotal), latency: avg(llmLatencySum, llmCalls), calls: llmCalls },
    ];
  }, [data]);

  function clampPct(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  }

  function fmtMs(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "0 ms";
    if (n >= 100) return `${Math.round(n)} ms`;
    return `${n.toFixed(1)} ms`;
  }

  return (
    <div
      style={{
        fontFamily: "ui-sans-serif, system-ui",
        padding: 24,
        minHeight: "100vh",
        boxSizing: "border-box",
        background: "#f8fafc",
      }}
    >
      <div style={{ maxWidth: 1600, margin: "0 auto", height: "100%" }}>
        <h1 style={{ margin: 0, fontSize: 24, textAlign: "center" }}>Semantic Cache Metrics</h1>

        <div style={{ marginTop: 20 }}>
          {error ? (
            <pre style={{ color: "#b91c1c", margin: 0 }}>{error}</pre>
          ) : !data ? (
            <div style={{ textAlign: "center", color: "#475569" }}>Loading…</div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gap: 24,
                alignItems: "stretch",
                minHeight: "78vh",
              }}
            >
              {cards.map((c) => {
                const pct = clampPct(c.pct);
                const ringBg = `conic-gradient(#0ea5e9 ${pct}%, #e2e8f0 0)`;

                return (
                  <div
                    key={c.key}
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: 16,
                      padding: 28,
                      background: "#fff",
                      boxShadow: "0 8px 24px rgba(15, 23, 42, 0.08)",
                      display: "flex",
                      flexDirection: "column",
                    }}
                  >
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 20, fontWeight: 900, letterSpacing: 0.5, color: "#0f172a" }}>
                        {c.title}
                      </div>
                      <div style={{ marginTop: 4, fontSize: 13, color: "#64748b" }}>{c.calls} requests</div>
                    </div>

                    <div style={{ flex: 1, display: "grid", gridTemplateRows: "1fr 1fr", rowGap: 18, marginTop: 18 }}>
                      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
                        <div style={{ fontSize: 13, color: "#64748b", textAlign: "center" }}>Hit percent</div>
                        <div style={{ marginTop: 14, display: "grid", placeItems: "center" }}>
                          <div
                            style={{
                              width: 180,
                              height: 180,
                              borderRadius: 999,
                              background: ringBg,
                              display: "grid",
                              placeItems: "center",
                            }}
                            aria-label={`${c.title} hit percent ${pct.toFixed(1)}%`}
                          >
                            <div
                              style={{
                                width: 140,
                                height: 140,
                                borderRadius: 999,
                                background: "#fff",
                                display: "grid",
                                placeItems: "center",
                                border: "1px solid #e2e8f0",
                              }}
                            >
                              <div style={{ fontSize: 22, fontWeight: 900, color: "#0f172a" }}>{pct.toFixed(0)}%</div>
                            </div>
                          </div>
                        </div>
                        <div style={{ marginTop: 10, fontSize: 13, color: "#64748b", textAlign: "center" }}>
                          {c.key === "llm" ? "LLM calls" : "Cache hits"}
                        </div>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
                        <div style={{ fontSize: 13, color: "#64748b", textAlign: "center" }}>Avg latency</div>
                        <div style={{ marginTop: 10, textAlign: "center", fontSize: 34, fontWeight: 950, color: "#0f172a" }}>
                          {fmtMs(c.latency)}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

