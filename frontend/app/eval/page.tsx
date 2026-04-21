"use client";
import useSWR from "swr";
import Link from "next/link";
import {
  CheckCircle2, XCircle, AlertTriangle, ExternalLink,
  RefreshCw, ArrowRight, BarChart2,
} from "lucide-react";
import { motion } from "framer-motion";
import { API_BASE, LANGFUSE_URL } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type Stats = {
  total_reports: number;
  passed_reports: number;
  avg_relevancy: number | null;
  avg_duration_sec: number | null;
  total_tokens_in: number | null;
  total_tokens_out: number | null;
};

type EvalRow = {
  id: string;
  company_name: string;
  industry: string | null;
  website: string | null;
  sources_used: string[];
  validation_passed: boolean | null;
  relevancy_score: number | null;
  token_count_in: number | null;
  token_count_out: number | null;
  retry_count: number | null;
  duration_sec: number | null;
  session_status: string | null;
  created_at: string;
};

function fetchStats(): Promise<Stats> {
  return fetch(`${API_BASE}/api/stats`).then(r => r.json());
}
function fetchEval(): Promise<{ rows: EvalRow[] }> {
  return fetch(`${API_BASE}/api/eval`).then(r => r.json());
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  color?: string;
}) {
  return (
    <div
      className="rounded-xl px-4 py-4"
      style={{
        background: "var(--bg-panel)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      <p style={{ fontSize: 11, color: "var(--text-subtle)", fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </p>
      <p style={{ fontSize: 26, fontWeight: 510, letterSpacing: "-0.02em", color: color ?? "var(--text-primary)" }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 11, color: "var(--text-subtle)", marginTop: 2 }}>{sub}</p>}
    </div>
  );
}

function ScoreBadge({ score, passed }: { score: number | null; passed: boolean | null }) {
  if (score === null) return <span style={{ color: "var(--text-subtle)", fontSize: 12 }}>—</span>;
  const pct = Math.round(score * 100);
  const color = passed ? "var(--green)" : "var(--yellow)";
  return (
    <span
      className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
      style={{
        background: passed ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)",
        border: `1px solid ${passed ? "rgba(16,185,129,0.2)" : "rgba(245,158,11,0.2)"}`,
        color,
        fontWeight: 510,
      }}
    >
      {passed ? <CheckCircle2 size={9} /> : <AlertTriangle size={9} />}
      {pct}%
    </span>
  );
}

function ValidationIcon({ passed }: { passed: boolean | null }) {
  if (passed === true)  return <CheckCircle2 size={14} style={{ color: "var(--green)" }} />;
  if (passed === false) return <XCircle size={14} style={{ color: "var(--red)" }} />;
  return <span style={{ color: "var(--text-subtle)", fontSize: 12 }}>—</span>;
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function EvalPage() {
  const { data: stats, isLoading: statsLoading, mutate: refetchStats } = useSWR<Stats>("eval-stats", fetchStats, { refreshInterval: 0, shouldRetryOnError: false });
  const { data: evalData, isLoading: evalLoading, mutate: refetchEval } = useSWR<{ rows: EvalRow[] }>("eval-rows", fetchEval, { refreshInterval: 0, shouldRetryOnError: false });

  const rows = evalData?.rows ?? [];
  const isLoading = statsLoading || evalLoading;

  function refresh() { refetchStats(); refetchEval(); }

  const passRate = stats && Number(stats.total_reports) > 0
    ? Math.round((Number(stats.passed_reports) / Number(stats.total_reports)) * 100)
    : null;

  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between mb-8 gap-4"
        >
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 510, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
              Evaluation
            </h1>
            <p style={{ fontSize: 14, color: "var(--text-muted)", marginTop: 4 }}>
              Agent output quality across all research runs.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {/* Deep-link to Langfuse */}
            <a
              href={LANGFUSE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
              style={{
                background: "rgba(99,102,241,0.1)",
                border: "1px solid rgba(99,102,241,0.22)",
                color: "var(--accent-vivid)",
                fontWeight: 510,
                textDecoration: "none",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "rgba(99,102,241,0.18)")}
              onMouseLeave={e => (e.currentTarget.style.background = "rgba(99,102,241,0.1)")}
            >
              <BarChart2 size={11} />
              Open Langfuse
              <ExternalLink size={9} />
            </a>
            <button
              onClick={refresh}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg cursor-pointer"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-default)",
                color: "var(--text-muted)",
                fontWeight: 510,
              }}
            >
              <RefreshCw size={11} className={isLoading ? "spin-ring" : ""} />
              Refresh
            </button>
          </div>
        </motion.div>

        {/* Stats cards */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 gap-3 mb-8 sm:grid-cols-4"
        >
          <StatCard
            label="Total reports"
            value={stats ? String(stats.total_reports) : "—"}
          />
          <StatCard
            label="Pass rate"
            value={passRate !== null ? `${passRate}%` : "—"}
            color={passRate !== null ? (passRate >= 70 ? "var(--green)" : "var(--yellow)") : undefined}
          />
          <StatCard
            label="Avg relevancy"
            value={stats?.avg_relevancy != null
              ? `${Math.round(Number(stats.avg_relevancy) * 100)}%`
              : "—"}
            color="var(--accent-vivid)"
          />
          <StatCard
            label="Avg duration"
            value={stats?.avg_duration_sec != null
              ? `${Number(stats.avg_duration_sec).toFixed(0)}s`
              : "—"}
            sub={stats?.total_tokens_in != null
              ? `${((Number(stats.total_tokens_in) + Number(stats.total_tokens_out || 0)) / 1000).toFixed(0)}k tokens total`
              : undefined}
          />
        </motion.div>

        {/* Langfuse callout */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="rounded-xl px-4 py-3 mb-6 flex items-center gap-3"
          style={{
            background: "rgba(99,102,241,0.05)",
            border: "1px solid rgba(99,102,241,0.15)",
          }}
        >
          <BarChart2 size={14} style={{ color: "var(--accent-vivid)", flexShrink: 0 }} />
          <div className="flex-1 min-w-0">
            <p style={{ fontSize: 13, color: "var(--text-body)", fontWeight: 510 }}>
              Detailed LLM traces, spans, and scoring live in Langfuse
            </p>
            <p style={{ fontSize: 12, color: "var(--text-subtle)", marginTop: 1 }}>
              Every research run is traced end-to-end — classification, scraping, generation, and validation spans with token counts and latency.
            </p>
          </div>
          <a
            href={LANGFUSE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg cursor-pointer"
            style={{
              background: "var(--accent)",
              color: "#fff",
              fontWeight: 510,
              textDecoration: "none",
            }}
          >
            Open console <ExternalLink size={10} />
          </a>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl overflow-hidden"
          style={{
            background: "var(--bg-panel)",
            border: "1px solid var(--border-default)",
          }}
        >
          {/* Table header */}
          <div
            className="grid px-4 py-2.5"
            style={{
              gridTemplateColumns: "1fr 100px 100px 60px 60px 64px 80px 28px",
              borderBottom: "1px solid var(--border-subtle)",
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.07em",
              textTransform: "uppercase",
              color: "var(--text-subtle)",
            }}
          >
            <span>Company</span>
            <span>Score</span>
            <span>Validated</span>
            <span>Retries</span>
            <span>Dur.</span>
            <span>Tokens</span>
            <span>Date</span>
            <span />
          </div>

          {/* Loading */}
          {evalLoading && (
            <div className="px-4 py-8 text-center" style={{ fontSize: 13, color: "var(--text-subtle)" }}>
              Loading…
            </div>
          )}

          {/* Empty */}
          {!evalLoading && rows.length === 0 && (
            <div className="px-4 py-12 flex flex-col items-center gap-2">
              <p style={{ fontSize: 14, color: "var(--text-muted)" }}>No reports yet.</p>
              <Link href="/" style={{ fontSize: 13, color: "var(--accent-vivid)", textDecoration: "none" }}>
                Research a company →
              </Link>
            </div>
          )}

          {/* Rows */}
          {rows.map((row, i) => {
            const date = row.created_at
              ? new Date(row.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })
              : "—";
            const tokens = (Number(row.token_count_in ?? 0) + Number(row.token_count_out ?? 0));
            const tokensStr = tokens > 0 ? `${(tokens / 1000).toFixed(1)}k` : "—";
            const dur = row.duration_sec != null ? `${Number(row.duration_sec).toFixed(0)}s` : "—";

            return (
              <motion.div
                key={row.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                className="grid px-4 py-3 items-center group transition-colors"
                style={{
                  gridTemplateColumns: "1fr 100px 100px 60px 60px 64px 80px 28px",
                  borderBottom: i < rows.length - 1 ? "1px solid var(--border-subtle)" : "none",
                  cursor: "pointer",
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--surface-card)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                {/* Company */}
                <div className="min-w-0 pr-2">
                  <div style={{ fontSize: 13, fontWeight: 510, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {row.company_name}
                  </div>
                  {row.industry && (
                    <div style={{ fontSize: 11, color: "var(--text-subtle)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {row.industry}
                    </div>
                  )}
                </div>

                {/* Score */}
                <div><ScoreBadge score={row.relevancy_score} passed={row.validation_passed} /></div>

                {/* Validated */}
                <div><ValidationIcon passed={row.validation_passed} /></div>

                {/* Retries */}
                <div style={{ fontSize: 12, color: Number(row.retry_count) > 0 ? "var(--yellow)" : "var(--text-subtle)" }}>
                  {row.retry_count ?? 0}
                </div>

                {/* Duration */}
                <div style={{ fontSize: 12, color: "var(--text-subtle)" }}>{dur}</div>

                {/* Tokens */}
                <div style={{ fontSize: 12, color: "var(--text-subtle)" }}>{tokensStr}</div>

                {/* Date */}
                <div style={{ fontSize: 11, color: "var(--text-subtle)" }}>{date}</div>

                {/* Link */}
                <Link
                  href={`/reports/${row.id}`}
                  className="flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                  style={{ color: "var(--text-subtle)", textDecoration: "none" }}
                  onClick={e => e.stopPropagation()}
                >
                  <ArrowRight size={13} />
                </Link>
              </motion.div>
            );
          })}
        </motion.div>

      </div>
    </main>
  );
}
