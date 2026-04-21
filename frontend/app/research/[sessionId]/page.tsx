"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useResearchStream } from "@/hooks/useResearchStream";
import Link from "next/link";
import {
  CheckCircle2, XCircle, Loader2, Globe, Search,
  Database, Brain, ShieldCheck, Save, AlertCircle, Cpu,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const STAGE_META: Record<string, { label: string; icon: React.ElementType }> = {
  classifying:   { label: "Classifying input",       icon: Search },
  resolving:     { label: "Resolving product owner", icon: Globe },
  scraping:      { label: "Scraping sources",        icon: Database },
  source_result: { label: "Source",                  icon: Globe },
  generating:    { label: "Generating report",       icon: Brain },
  validating:    { label: "Validating",              icon: ShieldCheck },
  retry:         { label: "Retrying",                icon: Loader2 },
  storing:       { label: "Saving",                  icon: Save },
  complete:      { label: "Complete",                icon: CheckCircle2 },
  error:         { label: "Error",                   icon: XCircle },
};

// Ordered list of stages for progress bar
const STAGE_ORDER = ["classifying", "resolving", "scraping", "generating", "validating", "storing", "complete"];

function stageProgress(events: { stage: string }[]): number {
  const stages = events.map(e => e.stage).filter(s => STAGE_ORDER.includes(s));
  const last = [...stages].reverse().find(s => STAGE_ORDER.includes(s));
  if (!last) return 0;
  const idx = STAGE_ORDER.indexOf(last);
  return Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
}

function StepIcon({ stage, isActive }: { stage: string; isActive: boolean }) {
  const color =
    stage === "error" ? "var(--red)"
    : stage === "complete" ? "var(--green)"
    : "var(--accent-vivid)";

  const bgColor =
    stage === "error" ? "rgba(239,68,68,0.1)"
    : stage === "complete" ? "rgba(16,185,129,0.1)"
    : "rgba(113,112,255,0.1)";

  const Meta = STAGE_META[stage] ?? STAGE_META["classifying"];
  const Icon = Meta.icon;

  return (
    <span
      className="flex items-center justify-center w-7 h-7 rounded-full shrink-0 relative"
      style={{ background: bgColor, border: `1px solid ${color}22` }}
    >
      {isActive && stage !== "complete" && stage !== "error" ? (
        <>
          {/* Ripple ring */}
          <span
            className="absolute inset-0 rounded-full"
            style={{ border: `1.5px solid ${color}`, animation: "pulse-ring 1.8s ease-out infinite" }}
          />
          <span className="pulse-dot w-2 h-2 rounded-full" style={{ background: color }} />
        </>
      ) : (
        <Icon size={13} style={{ color }} />
      )}
    </span>
  );
}

export default function ResearchPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { events, isComplete, isError, errorMsg, reportId } = useResearchStream(sessionId);

  useEffect(() => {
    if (isComplete && reportId) {
      setTimeout(() => router.push(`/reports/${reportId}`), 1200);
    }
  }, [isComplete, reportId, router]);

  const lastIdx = events.length - 1;
  const progress = isComplete ? 100 : stageProgress(events);

  return (
    <main
      className="min-h-screen flex flex-col items-center justify-start px-4 py-12"
      style={{ background: "var(--bg-canvas)" }}
    >
      {/* Session chip */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-xl mb-6 flex items-center justify-between"
      >
        <span style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 510 }}>
          Research session
        </span>
        <span
          className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
          style={{
            background: "var(--surface-overlay)",
            border: "1px solid var(--border-subtle)",
            color: "var(--text-subtle)",
            fontFamily: "monospace",
          }}
        >
          <Cpu size={10} />
          {sessionId?.slice(0, 8)}…
        </span>
      </motion.div>

      {/* Main card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-xl rounded-2xl overflow-hidden"
        style={{
          background: "var(--bg-panel)",
          border: "1px solid var(--border-default)",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.03), 0 20px 40px rgba(0,0,0,0.35)",
        }}
      >
        {/* Header with status */}
        <div
          className="px-5 py-4 flex items-center gap-3"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <span
            className="flex items-center gap-2.5"
            style={{ color: "var(--text-primary)", fontWeight: 510, fontSize: 15 }}
          >
            {isError ? (
              <XCircle size={15} style={{ color: "var(--red)" }} />
            ) : isComplete ? (
              <CheckCircle2 size={15} style={{ color: "var(--green)" }} />
            ) : (
              <Loader2 size={15} className="spin-ring" style={{ color: "var(--accent-vivid)" }} />
            )}
            {isError ? "Research failed" : isComplete ? "Research complete" : "Agent working…"}
          </span>

          {!isComplete && !isError && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="ml-auto text-xs px-2 py-0.5 rounded-full flex items-center gap-1.5"
              style={{
                background: "rgba(113,112,255,0.1)",
                border: "1px solid rgba(113,112,255,0.2)",
                color: "var(--accent-vivid)",
                fontWeight: 510,
              }}
            >
              <span className="pulse-dot w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-vivid)" }} />
              Live
            </motion.span>
          )}
        </div>

        {/* Progress bar */}
        <div style={{ height: 2, background: "var(--border-subtle)" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{
              height: "100%",
              background: isError
                ? "var(--red)"
                : isComplete
                ? "var(--green)"
                : "linear-gradient(90deg, var(--accent) 0%, var(--accent-vivid) 100%)",
            }}
          />
        </div>

        {/* Steps timeline */}
        <div className="px-5 py-5 space-y-0.5">
          {events.length === 0 && !isError && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3 py-3"
            >
              <span className="pulse-dot w-2 h-2 rounded-full shrink-0" style={{ background: "var(--accent-vivid)" }} />
              <span style={{ fontSize: 14, color: "var(--text-muted)" }}>Connecting to agent…</span>
            </motion.div>
          )}

          <AnimatePresence initial={false}>
            {events.map((ev, i) => {
              if (ev.stage === "source_result") return null;

              const isLast = i === lastIdx;
              const isActive = isLast && !isComplete && !isError;
              const meta = STAGE_META[ev.stage] ?? { label: ev.stage, icon: AlertCircle };

              const followingSources = ev.stage === "scraping"
                ? events.slice(i + 1).filter(e => e.stage === "source_result")
                : [];

              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                >
                  <div
                    className="flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors"
                    style={{
                      background: isActive ? "rgba(113,112,255,0.05)" : "transparent",
                    }}
                  >
                    <StepIcon stage={ev.stage} isActive={isActive} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 mb-0.5">
                        <span style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color:
                            ev.stage === "error" ? "var(--red)"
                            : ev.stage === "complete" ? "var(--green)"
                            : ev.stage === "retry" ? "var(--yellow)"
                            : "var(--text-subtle)",
                          textTransform: "uppercase",
                          letterSpacing: "0.07em",
                        }}>
                          {meta.label}
                        </span>
                      </div>
                      <p style={{ fontSize: 13.5, color: "var(--text-body)", lineHeight: 1.5 }}>
                        {ev.message}
                      </p>

                      {/* Source badges */}
                      {followingSources.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.1 }}
                          className="flex flex-wrap gap-1.5 mt-2"
                        >
                          {followingSources.map((s, si) => (
                            <motion.span
                              key={si}
                              initial={{ opacity: 0, scale: 0.88 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: si * 0.06 }}
                              className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                              style={{
                                background: s.status === "success"
                                  ? "rgba(16,185,129,0.08)"
                                  : "var(--surface-raised)",
                                border: `1px solid ${s.status === "success" ? "rgba(16,185,129,0.2)" : "var(--border-subtle)"}`,
                                color: s.status === "success" ? "var(--green)" : "var(--text-subtle)",
                                fontWeight: 510,
                              }}
                            >
                              <span
                                className="w-1.5 h-1.5 rounded-full"
                                style={{ background: s.status === "success" ? "var(--green)" : "var(--text-subtle)" }}
                              />
                              {s.source}
                            </motion.span>
                          ))}
                        </motion.div>
                      )}
                    </div>
                  </div>

                  {/* Connector line */}
                  {i < lastIdx && ev.stage !== "source_result" && (
                    <div
                      className="my-0.5 w-px h-3"
                      style={{ background: "var(--border-subtle)", marginLeft: "1.375rem" }}
                    />
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <AnimatePresence>
          {(isComplete || isError) && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              transition={{ duration: 0.25 }}
              className="px-5 py-3 flex items-center justify-between"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              {isComplete && reportId ? (
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Redirecting to report…
                </span>
              ) : (
                <span style={{ fontSize: 13, color: "var(--red)" }}>{errorMsg}</span>
              )}
              <Link
                href="/"
                className="text-sm px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                style={{
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-body)",
                  fontWeight: 510,
                  textDecoration: "none",
                }}
              >
                Try another
              </Link>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Progress label */}
      {!isComplete && !isError && events.length > 0 && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-4"
          style={{ fontSize: 12, color: "var(--text-subtle)" }}
        >
          {progress}% complete
        </motion.p>
      )}
    </main>
  );
}
