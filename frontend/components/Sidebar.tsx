"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, FileText, Database, Settings, Activity, FlaskConical } from "lucide-react";
import useSWR from "swr";
import { API_BASE } from "@/lib/api";

const NAV = [
  { href: "/",        icon: Search,        label: "Research" },
  { href: "/reports", icon: FileText,      label: "Reports"  },
  { href: "/eval",    icon: FlaskConical,  label: "Eval"     },
  { href: "/sources", icon: Database,      label: "Sources"  },
  { href: "/settings",icon: Settings,      label: "Settings" },
];

function useHealth() {
  return useSWR(
    "health",
    () => fetch(`${API_BASE}/api/health`).then((r) => r.json()),
    { refreshInterval: 30_000, shouldRetryOnError: false },
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { data: health, error: healthError } = useHealth();

  const allOk =
    health &&
    !healthError &&
    health.db === true &&
    health.qdrant === true &&
    health.ollama === true;

  const statusColor =
    healthError || !health
      ? "var(--text-subtle)"
      : allOk
      ? "var(--green)"
      : "var(--yellow)";

  const statusLabel =
    healthError || !health
      ? "Offline"
      : allOk
      ? "All systems OK"
      : "Degraded";

  return (
    <aside
      className="shrink-0 flex flex-col h-screen sticky top-0 overflow-y-auto"
      style={{
        width: 200,
        background: "var(--bg-panel)",
        borderRight: "1px solid var(--border-subtle)",
      }}
    >
      {/* Logo */}
      <div
        className="px-4 h-12 flex items-center shrink-0"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <span
          style={{
            color: "var(--text-primary)",
            fontWeight: 510,
            fontSize: 14,
            letterSpacing: "-0.02em",
          }}
        >
          Scout
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors"
              style={{
                color: active ? "var(--text-primary)" : "var(--text-muted)",
                background: active
                  ? "var(--surface-active)"
                  : "transparent",
                fontWeight: active ? 510 : 400,
                textDecoration: "none",
              }}
            >
              <Icon
                size={14}
                style={{
                  color: active ? "var(--accent-vivid)" : "var(--text-subtle)",
                  flexShrink: 0,
                }}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Health indicator */}
      <div
        className="px-4 py-3 shrink-0"
        style={{ borderTop: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: statusColor }}
          />
          <span style={{ fontSize: 11, color: "var(--text-subtle)", fontWeight: 510 }}>
            {statusLabel}
          </span>
          <Activity size={10} style={{ color: "var(--text-subtle)", marginLeft: "auto" }} />
        </div>
        {health && !allOk && !healthError && (
          <div className="mt-1.5 space-y-0.5">
            {[
              { key: "db",     label: "Database" },
              { key: "qdrant", label: "Qdrant"   },
              { key: "ollama", label: "Ollama"   },
            ].map(({ key, label }) => (
              <div key={key} className="flex items-center gap-1.5">
                <span
                  className="w-1 h-1 rounded-full"
                  style={{
                    background: health[key] ? "var(--green)" : "var(--red)",
                  }}
                />
                <span style={{ fontSize: 10, color: "var(--text-subtle)" }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
