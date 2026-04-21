"use client";
import useSWR from "swr";
import {
  CheckCircle2, XCircle, AlertTriangle, RefreshCw,
  Globe, Database, Users, Search,
} from "lucide-react";
import { API_BASE } from "@/lib/api";

const SOURCE_META: Record<
  string,
  { label: string; icon: React.ElementType; description: string; type: string }
> = {
  wikidata:       { label: "Wikidata",       icon: Globe,     description: "Free SPARQL knowledge graph. Founders, industry, HQ, website.",   type: "API"     },
  opencorporates: { label: "OpenCorporates", icon: Database,  description: "Global company registry. Legal name, status, registration.",       type: "API"     },
  crunchbase:     { label: "Crunchbase",     icon: Database,  description: "Startup funding rounds, investors, valuations.",                   type: "API"     },
  linkedin:       { label: "LinkedIn",       icon: Users,     description: "Company overview, employee count, industry. Stealth scraper.",     type: "Scraper" },
  duckduckgo:     { label: "DuckDuckGo",     icon: Search,    description: "Free web search. General, financial, and contact queries (3 each).", type: "Search"  },
};

type HealthData = {
  status: string;
  db: boolean;
  qdrant: boolean;
  ollama: boolean;
  sources?: Record<string, { reachable: boolean; latency_ms?: number }>;
};

function fetcher() {
  return fetch(`${API_BASE}/api/health`).then((r) => r.json()) as Promise<HealthData>;
}

function StatusBadge({ ok }: { ok: boolean | null }) {
  if (ok === null) {
    return (
      <span
        className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
        style={{
          background: "var(--surface-raised)",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-subtle)",
          fontWeight: 510,
        }}
      >
        <AlertTriangle size={9} /> Unknown
      </span>
    );
  }
  return (
    <span
      className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
      style={{
        background: ok ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
        border: `1px solid ${ok ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`,
        color: ok ? "var(--green)" : "var(--red)",
        fontWeight: 510,
      }}
    >
      {ok ? <CheckCircle2 size={9} /> : <XCircle size={9} />}
      {ok ? "Reachable" : "Unreachable"}
    </span>
  );
}

export default function SourcesPage() {
  const { data, isLoading, mutate } = useSWR<HealthData>("sources-health", fetcher, {
    refreshInterval: 60_000,
  });

  const sources = data?.sources ?? {};

  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-3xl mx-auto px-6 py-10">
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
              Data Sources
            </h1>
            <p style={{ fontSize: 14, color: "var(--text-muted)", marginTop: 4 }}>
              All sources the agent uses when researching a company.
            </p>
          </div>
          <button
            onClick={() => mutate()}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors"
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

        {/* Infrastructure */}
        <div className="mb-6">
          <p
            style={{
              fontSize: 11,
              fontWeight: 510,
              color: "var(--text-subtle)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 8,
            }}
          >
            Infrastructure
          </p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Database",   key: "db"     },
              { label: "Qdrant",     key: "qdrant" },
              { label: "Ollama LLM", key: "ollama" },
            ].map(({ label, key }) => (
              <div
                key={key}
                className="px-3 py-2.5 rounded-lg flex items-center justify-between"
                style={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <span style={{ fontSize: 13, color: "var(--text-body)", fontWeight: 510 }}>{label}</span>
                <StatusBadge ok={data ? (data[key as keyof HealthData] as boolean) : null} />
              </div>
            ))}
          </div>
        </div>

        {/* Sources */}
        <div>
          <p
            style={{
              fontSize: 11,
              fontWeight: 510,
              color: "var(--text-subtle)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 8,
            }}
          >
            Research Sources
          </p>
          <div className="space-y-2">
            {Object.entries(SOURCE_META).map(([key, meta]) => {
              const Icon = meta.icon;
              const sourceData = sources[key];
              const reachable = sourceData?.reachable ?? null;

              return (
                <div
                  key={key}
                  className="px-4 py-3 rounded-xl flex items-center gap-4"
                  style={{
                    background: "var(--surface-card)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <span
                    className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
                    style={{
                      background: "rgba(113,112,255,0.08)",
                      border: "1px solid rgba(113,112,255,0.15)",
                    }}
                  >
                    <Icon size={14} style={{ color: "var(--accent-vivid)" }} />
                  </span>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span style={{ fontSize: 14, fontWeight: 510, color: "var(--text-primary)" }}>
                        {meta.label}
                      </span>
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: "var(--surface-raised)",
                          color: "var(--text-subtle)",
                          fontWeight: 510,
                        }}
                      >
                        {meta.type}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-subtle)", marginTop: 1 }}>
                      {meta.description}
                    </p>
                    {sourceData?.latency_ms !== undefined && (
                      <span style={{ fontSize: 11, color: "var(--text-subtle)" }}>
                        {sourceData.latency_ms}ms
                      </span>
                    )}
                  </div>

                  <StatusBadge ok={reachable} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </main>
  );
}
