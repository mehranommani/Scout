"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { startResearch } from "@/lib/api";
import { Search, ArrowRight, FileText, CheckCircle2, Star } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import useSWR from "swr";
import { API_BASE } from "@/lib/api";

const EXAMPLES = ["Stripe", "OpenAI", "Linear", "Notion", "Figma", "Vercel"];

const PLACEHOLDERS = [
  "Search Stripe…",
  "Search OpenAI…",
  "Search Linear…",
  "Search Notion…",
  "Search any company…",
];

type Stats = { total_reports: number; passed_reports: number; avg_relevancy: number | null; avg_duration_sec: number | null };
function useStats() {
  return useSWR<Stats>("home-stats", () =>
    fetch(`${API_BASE}/api/stats`).then(r => r.json()),
    { refreshInterval: 0, shouldRetryOnError: false },
  );
}

export default function HomePage() {
  const router = useRouter();
  const { data: stats } = useStats();
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phIdx, setPhIdx] = useState(0);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Cycle placeholder text when input is empty and not focused
  useEffect(() => {
    if (focused || name) return;
    const id = setInterval(() => setPhIdx(i => (i + 1) % PLACEHOLDERS.length), 2400);
    return () => clearInterval(id);
  }, [focused, name]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await startResearch(name.trim());
      router.push(`/research/${res.session_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <main
      className="relative min-h-screen flex flex-col items-center justify-center px-6 overflow-hidden"
      style={{ background: "var(--bg-canvas)" }}
    >
      {/* Subtle grid overlay */}
      <div className="hero-grid absolute inset-0 pointer-events-none" style={{ opacity: 0.4 }} />

      {/* Radial glow behind content */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse 60% 50% at 50% 40%, rgba(99,102,241,0.07) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 w-full max-w-2xl">

        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="flex justify-center mb-8"
        >
          <span
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs"
            style={{
              background: "rgba(99,102,241,0.1)",
              border: "1px solid rgba(99,102,241,0.22)",
              color: "var(--accent-vivid)",
              fontWeight: 510,
              letterSpacing: "0.01em",
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full pulse-dot"
              style={{ background: "var(--accent-vivid)" }}
            />
            AI-powered company intelligence
          </span>
        </motion.div>

        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05, ease: "easeOut" }}
          className="text-center mb-4"
        >
          <h1
            style={{
              fontSize: "clamp(32px, 5.5vw, 52px)",
              fontWeight: 510,
              letterSpacing: "-0.03em",
              lineHeight: 1.08,
              color: "var(--text-primary)",
            }}
          >
            Research any company
            <br />
            <span className="gradient-text-accent">in seconds.</span>
          </h1>
        </motion.div>

        {/* Sub */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="text-center mb-10"
          style={{ fontSize: 15, color: "var(--text-muted)", lineHeight: 1.65, maxWidth: 420, margin: "0 auto 2.5rem" }}
        >
          Enter a company or product name. The agent scrapes public sources,
          validates the data, and produces a structured intelligence report.
        </motion.p>

        {/* Search form */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.2 }}
        >
          <form onSubmit={handleSubmit} className="relative">
            <div
              className="focus-ring rounded-xl transition-all"
              style={{
                background: "var(--surface-overlay)",
                border: `1px solid ${focused ? "rgba(113,112,255,0.45)" : "var(--border-default)"}`,
                transition: "border-color 0.2s, box-shadow 0.2s",
              }}
            >
              {/* Search icon */}
              <div className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: "var(--text-subtle)", pointerEvents: "none" }}>
                <Search size={15} />
              </div>

              <input
                ref={inputRef}
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                disabled={loading}
                className="w-full bg-transparent outline-none pl-10 pr-36 py-4 text-sm"
                style={{
                  color: "var(--text-primary)",
                  caretColor: "var(--accent-vivid)",
                  fontWeight: 400,
                }}
                placeholder={PLACEHOLDERS[phIdx]}
                aria-label="Company or product name"
              />

              {/* Submit button */}
              <button
                type="submit"
                disabled={loading || !name.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition-all cursor-pointer"
                style={{
                  background: loading || !name.trim() ? "rgba(94,106,210,0.35)" : "var(--accent)",
                  color: "#fff",
                  fontWeight: 510,
                  cursor: loading || !name.trim() ? "not-allowed" : "pointer",
                  transition: "background 0.2s",
                }}
                aria-label="Run research"
              >
                {loading ? (
                  <>
                    <svg className="spin-ring" width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                      <circle cx="7" cy="7" r="5.5" stroke="var(--spinner-track)" strokeWidth="1.5"/>
                      <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    Researching
                  </>
                ) : (
                  <>Research <ArrowRight size={12} /></>
                )}
              </button>
            </div>
          </form>
        </motion.div>

        {/* Example pills */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.32 }}
          className="flex items-center justify-center gap-2 flex-wrap mt-4"
        >
          <span style={{ fontSize: 11, color: "var(--text-subtle)", fontWeight: 510 }}>Try:</span>
          {EXAMPLES.map((ex, i) => (
            <motion.button
              key={ex}
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.35 + i * 0.04 }}
              onClick={() => { setName(ex); inputRef.current?.focus(); }}
              className="rounded-full px-3 py-1 text-xs transition-all cursor-pointer"
              style={{
                background: "transparent",
                border: "1px solid var(--border-solid)",
                color: "var(--text-muted)",
                fontWeight: 510,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = "var(--text-primary)";
                e.currentTarget.style.borderColor = "var(--border-default)";
                e.currentTarget.style.background = "var(--surface-card)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = "var(--text-muted)";
                e.currentTarget.style.borderColor = "var(--border-solid)";
                e.currentTarget.style.background = "transparent";
              }}
            >
              {ex}
            </motion.button>
          ))}
        </motion.div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mt-5 rounded-lg px-4 py-3 text-sm"
              style={{
                background: "rgba(239,68,68,0.07)",
                border: "1px solid rgba(239,68,68,0.2)",
                color: "#fca5a5",
              }}
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats strip — real data from backend */}
        {stats && Number(stats.total_reports) > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.55 }}
            className="flex items-center justify-center gap-8 mt-12"
          >
            <div className="flex items-center gap-2">
              <FileText size={12} style={{ color: "var(--text-subtle)" }} />
              <span style={{ fontSize: 12, color: "var(--text-subtle)" }}>
                <span style={{ color: "var(--text-muted)", fontWeight: 510 }}>{stats.total_reports}</span>
                {" "}reports
              </span>
            </div>
            {stats.avg_relevancy != null && (
              <div className="flex items-center gap-2">
                <Star size={12} style={{ color: "var(--text-subtle)" }} />
                <span style={{ fontSize: 12, color: "var(--text-subtle)" }}>
                  <span style={{ color: "var(--text-muted)", fontWeight: 510 }}>
                    {Math.round(Number(stats.avg_relevancy) * 100)}%
                  </span>
                  {" "}avg relevancy
                </span>
              </div>
            )}
            {stats.passed_reports != null && Number(stats.total_reports) > 0 && (
              <div className="flex items-center gap-2">
                <CheckCircle2 size={12} style={{ color: "var(--text-subtle)" }} />
                <span style={{ fontSize: 12, color: "var(--text-subtle)" }}>
                  <span style={{ color: "var(--text-muted)", fontWeight: 510 }}>
                    {Math.round((Number(stats.passed_reports) / Number(stats.total_reports)) * 100)}%
                  </span>
                  {" "}pass rate
                </span>
              </div>
            )}
          </motion.div>
        )}

      </div>
    </main>
  );
}
