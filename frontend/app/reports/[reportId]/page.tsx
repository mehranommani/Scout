"use client";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetchReport, type Report } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import {
  Globe, MapPin, Calendar, Users,
  CheckCircle2, AlertTriangle, ExternalLink, Database,
} from "lucide-react";
import { motion } from "framer-motion";

function fetcher(id: string) { return fetchReport(id); }

function MetaBadge({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div
      className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl transition-colors cursor-default"
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
      }}
      onMouseEnter={e => (e.currentTarget.style.background = "var(--surface-raised)")}
      onMouseLeave={e => (e.currentTarget.style.background = "var(--surface-card)")}
    >
      <Icon size={13} style={{ color: "var(--accent-vivid)", flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 9, fontWeight: 600, color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "0.07em" }}>
          {label}
        </div>
        <div style={{ fontSize: 13, color: "var(--text-body)", fontWeight: 510 }}>
          {value}
        </div>
      </div>
    </div>
  );
}

function ConfidenceGauge({ score, passed }: { score: number; passed: boolean | null }) {
  const color = passed ? "var(--green)" : "var(--yellow)";
  const bgColor = passed ? "rgba(16,185,129,0.1)" : "rgba(245,158,11,0.1)";
  const borderColor = passed ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)";

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-full"
      style={{ background: bgColor, border: `1px solid ${borderColor}` }}
    >
      {passed
        ? <CheckCircle2 size={12} style={{ color }} />
        : <AlertTriangle size={12} style={{ color }} />}
      <span style={{ fontSize: 12, color, fontWeight: 510 }}>{score}% confidence</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">
        {/* Header skeleton */}
        <div className="space-y-3">
          <div className="skeleton rounded-lg h-10 w-64" />
          <div className="skeleton rounded h-4 w-32" />
          <div className="flex gap-2 mt-4">
            {[120, 100, 110, 90].map(w => (
              <div key={w} className="skeleton rounded-xl h-12" style={{ width: w }} />
            ))}
          </div>
        </div>
        {/* Body skeleton */}
        <div className="skeleton rounded-xl h-96" />
      </div>
    </main>
  );
}

const fadeUp = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
};

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const { data, error, isLoading } = useSWR<Report>(reportId, fetcher);

  if (isLoading) return <LoadingSkeleton />;

  if (error || !data) {
    return (
      <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-canvas)" }}>
        <div style={{ color: "var(--red)", fontSize: 14 }}>Failed to load report.</div>
      </main>
    );
  }

  const score = data.relevancy_score != null ? Math.round(data.relevancy_score * 100) : null;
  const passed = data.validation_passed;

  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-3xl mx-auto px-6 py-10">

        {/* Company header */}
        <motion.div
          {...fadeUp}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="mb-8"
        >
          {/* Confidence badge + sources row */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            {score !== null && (
              <ConfidenceGauge score={score} passed={passed} />
            )}
            {data.sources_used?.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <Globe size={10} style={{ color: "var(--text-subtle)" }} />
                {data.sources_used.map(s => (
                  <span
                    key={s}
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={{
                      background: "var(--surface-raised)",
                      border: "1px solid var(--border-subtle)",
                      color: "var(--text-subtle)",
                      fontWeight: 510,
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Company name */}
          <h1
            style={{
              fontSize: "clamp(28px, 5vw, 42px)",
              fontWeight: 510,
              letterSpacing: "-0.025em",
              color: "var(--text-primary)",
              lineHeight: 1.08,
              marginBottom: 8,
            }}
          >
            {data.company_name}
          </h1>

          {/* Website */}
          {data.website && (
            <a
              href={data.website.startsWith("http") ? data.website : `https://${data.website}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm transition-colors"
              style={{ color: "var(--accent-vivid)", textDecoration: "none" }}
              onMouseEnter={e => (e.currentTarget.style.color = "var(--accent-hover)")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--accent-vivid)")}
            >
              {data.website.replace(/^https?:\/\//, "")}
              <ExternalLink size={11} />
            </a>
          )}

          {/* Meta badges */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.4 }}
            className="flex flex-wrap gap-2 mt-5"
          >
            {data.industry && <MetaBadge icon={Database} label="Industry" value={data.industry} />}
            {data.founded_date && <MetaBadge icon={Calendar} label="Founded" value={data.founded_date.slice(0, 10)} />}
            {(data as Report & { headquarters?: string }).headquarters && (
              <MetaBadge icon={MapPin} label="HQ" value={(data as Report & { headquarters?: string }).headquarters!} />
            )}
            {(data as Report & { employee_count?: number }).employee_count && (
              <MetaBadge icon={Users} label="Employees" value={String((data as Report & { employee_count?: number }).employee_count)} />
            )}
          </motion.div>
        </motion.div>

        {/* Divider */}
        <div style={{ height: 1, background: "var(--border-subtle)", marginBottom: 28 }} />

        {/* Report body */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="rounded-2xl px-7 py-7"
          style={{
            background: "var(--bg-panel)",
            border: "1px solid var(--border-default)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
          }}
        >
          <div
            className="prose prose-sm max-w-none"
            style={{
              "--tw-prose-body":     "var(--text-body)",
              "--tw-prose-headings": "var(--text-primary)",
              "--tw-prose-links":    "var(--accent-vivid)",
              "--tw-prose-bold":     "var(--text-primary)",
              "--tw-prose-bullets":  "var(--border-default)",
              "--tw-prose-hr":       "var(--border-solid)",
              "--tw-prose-pre-bg":   "var(--bg-surface)",
            } as React.CSSProperties}
          >
            <ReactMarkdown>{data.report_text}</ReactMarkdown>
          </div>
        </motion.div>

        {/* Footer meta */}
        {(data.token_count_in || data.token_count_out) ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
            className="mt-5 flex items-center gap-5"
            style={{ fontSize: 11, color: "var(--text-subtle)" }}
          >
            <span>Tokens in: <strong style={{ color: "var(--text-muted)" }}>{data.token_count_in ?? 0}</strong></span>
            <span>Tokens out: <strong style={{ color: "var(--text-muted)" }}>{data.token_count_out ?? 0}</strong></span>
          </motion.div>
        ) : null}

      </div>
    </main>
  );
}
