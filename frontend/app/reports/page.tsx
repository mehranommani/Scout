"use client";
import useSWR from "swr";
import { fetchReports } from "@/lib/api";
import Link from "next/link";
import { ArrowRight, Search, Calendar, CheckCircle2, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

function fetcher() { return fetchReports(); }

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 rounded-xl" style={{ border: "1px solid var(--border-subtle)" }}>
      <div className="skeleton w-2 h-2 rounded-full shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="skeleton h-3.5 rounded w-36" />
        <div className="skeleton h-2.5 rounded w-20" />
      </div>
      <div className="skeleton h-5 w-14 rounded-full" />
      <div className="skeleton h-3 w-20 rounded" />
    </div>
  );
}

export default function ReportsPage() {
  const { data, isLoading, error } = useSWR("reports", fetcher, { refreshInterval: 0 });
  const reports = data?.reports ?? [];

  return (
    <main className="min-h-screen" style={{ background: "var(--bg-canvas)" }}>
      <div className="max-w-3xl mx-auto px-6 py-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="mb-8"
        >
          <h1 style={{ fontSize: 28, fontWeight: 510, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
            Reports
          </h1>
          <p style={{ fontSize: 14, color: "var(--text-muted)", marginTop: 4 }}>
            {isLoading
              ? "Loading…"
              : reports.length > 0
              ? `${reports.length} company ${reports.length === 1 ? "report" : "reports"} generated`
              : "No reports yet"}
          </p>
        </motion.div>

        {error && (
          <p style={{ color: "var(--red)", fontSize: 14 }}>Failed to load reports.</p>
        )}

        {/* Loading skeletons */}
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map(i => <RowSkeleton key={i} />)}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && reports.length === 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-2xl flex flex-col items-center justify-center py-20 text-center"
            style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)" }}
          >
            <Search size={28} style={{ color: "var(--text-subtle)", marginBottom: 12 }} />
            <p style={{ fontSize: 15, color: "var(--text-muted)", fontWeight: 510 }}>No reports yet</p>
            <p style={{ fontSize: 13, color: "var(--text-subtle)", marginTop: 4 }}>
              Start by researching a company or product.
            </p>
            <Link
              href="/"
              className="mt-6 flex items-center gap-1.5 text-sm px-4 py-2 rounded-xl cursor-pointer"
              style={{ background: "var(--accent)", color: "#fff", fontWeight: 510, textDecoration: "none" }}
            >
              Research a company <ArrowRight size={13} />
            </Link>
          </motion.div>
        )}

        {/* Report rows */}
        {reports.length > 0 && (
          <div className="space-y-2">
            <AnimatePresence>
              {reports.map((r, i) => {
                const score = r.relevancy_score != null
                  ? Math.round(Number(r.relevancy_score) * 100)
                  : null;
                const passed = r.validation_passed;
                const date = r.created_at
                  ? new Date(String(r.created_at)).toLocaleDateString("en-US", {
                      month: "short", day: "numeric", year: "numeric",
                    })
                  : null;

                return (
                  <motion.div
                    key={String(r.id)}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.25 }}
                  >
                    <Link
                      href={`/reports/${r.id}`}
                      className="flex items-center gap-4 px-4 py-3 rounded-xl transition-all group cursor-pointer"
                      style={{
                        background: "var(--surface-card)",
                        border: "1px solid var(--border-subtle)",
                        textDecoration: "none",
                        display: "flex",
                        transition: "background 0.15s, border-color 0.15s",
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLElement).style.background = "var(--surface-raised)";
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLElement).style.background = "var(--surface-card)";
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border-subtle)";
                      }}
                    >
                      {/* Status dot */}
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: passed ? "var(--green)" : passed === false ? "var(--yellow)" : "var(--text-subtle)" }}
                      />

                      {/* Company info */}
                      <div className="flex-1 min-w-0">
                        <div style={{ fontSize: 14, fontWeight: 510, color: "var(--text-primary)" }}>
                          {r.company_name}
                        </div>
                        {r.industry && (
                          <div style={{ fontSize: 12, color: "var(--text-subtle)", marginTop: 1 }}>
                            {r.industry}
                          </div>
                        )}
                      </div>

                      {/* Score badge */}
                      {score !== null && (
                        <span
                          className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full shrink-0"
                          style={{
                            background: passed ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)",
                            border: `1px solid ${passed ? "rgba(16,185,129,0.2)" : "rgba(245,158,11,0.2)"}`,
                            color: passed ? "var(--green)" : "var(--yellow)",
                            fontWeight: 510,
                          }}
                        >
                          {passed ? <CheckCircle2 size={9} /> : <AlertTriangle size={9} />}
                          {score}%
                        </span>
                      )}

                      {/* Date */}
                      {date && (
                        <span
                          className="flex items-center gap-1 text-xs shrink-0"
                          style={{ color: "var(--text-subtle)", fontWeight: 510 }}
                        >
                          <Calendar size={10} /> {date}
                        </span>
                      )}

                      <ArrowRight
                        size={13}
                        className="shrink-0 transition-transform group-hover:translate-x-0.5"
                        style={{ color: "var(--text-subtle)" }}
                      />
                    </Link>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </main>
  );
}
