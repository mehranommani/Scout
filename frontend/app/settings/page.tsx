"use client";
import useSWR from "swr";
import { Cpu, Shield, Database, Search, RefreshCw } from "lucide-react";
import { API_BASE } from "@/lib/api";

type Config = {
  llm_model: string;
  llm_base_url: string;
  validation: {
    min_text_length: number;
    min_relevancy_score: number;
    max_retries: number;
  };
  sources: Record<string, { enabled: boolean; use_api?: boolean; use_scrapling?: boolean }>;
  search: {
    max_results_per_query: number;
    num_queries: number;
  };
};

function fetcher() {
  return fetch(`${API_BASE}/api/config`).then((r) => r.json()) as Promise<Config>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex items-center justify-between px-4 py-3"
      style={{ borderBottom: "1px solid var(--border-subtle)" }}
    >
      <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 510, fontFamily: "monospace" }}>
        {value}
      </span>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={13} style={{ color: "var(--accent-vivid)" }} />
        <p
          style={{
            fontSize: 11,
            fontWeight: 510,
            color: "var(--text-subtle)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {title}
        </p>
      </div>
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {children}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { data, isLoading, mutate } = useSWR<Config>("config", fetcher, {
    refreshInterval: 0,
    shouldRetryOnError: false,
  });

  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1
              style={{
                fontSize: 28,
                fontWeight: 510,
                letterSpacing: "-0.02em",
                color: "var(--text-primary)",
              }}
            >
              Settings
            </h1>
            <p style={{ fontSize: 14, color: "var(--text-muted)", marginTop: 4 }}>
              Agent configuration and validation thresholds (read-only).
            </p>
          </div>
          <button
            onClick={() => mutate()}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-default)",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontWeight: 510,
            }}
          >
            <RefreshCw size={11} className={isLoading ? "spin-ring" : ""} />
            Refresh
          </button>
        </div>

        {isLoading && (
          <p style={{ fontSize: 13, color: "var(--text-subtle)" }}>Loading config…</p>
        )}

        {!isLoading && !data && (
          <div
            className="rounded-xl px-4 py-3 text-sm"
            style={{
              background: "rgba(239,68,68,0.06)",
              border: "1px solid rgba(239,68,68,0.18)",
              color: "var(--red)",
            }}
          >
            Could not reach backend. Make sure the server is running on port 8000.
          </div>
        )}

        {data && (
          <>
            <Section icon={Cpu} title="LLM">
              <Row label="Model" value={data.llm_model} />
              <Row label="Base URL" value={data.llm_base_url} />
            </Section>

            <Section icon={Shield} title="Validation">
              <Row label="Min text length" value={`${data.validation.min_text_length} chars`} />
              <Row label="Min relevancy score" value={`${Math.round(data.validation.min_relevancy_score * 100)}%`} />
              <Row label="Max retries" value={data.validation.max_retries} />
            </Section>

            <Section icon={Search} title="Web Search (DuckDuckGo)">
              <Row label="Results per query" value={data.search?.max_results_per_query ?? "—"} />
              <Row label="Query categories" value={data.search?.num_queries ?? "—"} />
            </Section>

            <Section icon={Database} title="Sources">
              {Object.entries(data.sources ?? {}).map(([key, src]) => (
                <Row
                  key={key}
                  label={key.charAt(0).toUpperCase() + key.slice(1)}
                  value={
                    <span
                      style={{
                        color: src.enabled ? "var(--green)" : "var(--text-subtle)",
                      }}
                    >
                      {src.enabled ? "Enabled" : "Disabled"}
                    </span>
                  }
                />
              ))}
            </Section>
          </>
        )}
      </div>
    </main>
  );
}
