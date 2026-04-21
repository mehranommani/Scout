export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "http://localhost:3001";

export interface StartResearchResponse {
  session_id: string;
  status: string;
  stream_url: string;
}

export interface Report {
  id: string;
  session_id: string;
  company_name: string;
  industry: string | null;
  website: string | null;
  founded_date: string | null;
  founders: Array<{ name: string; role: string }>;
  funding_rounds: Array<{ round_type: string; amount_usd: number | null; announced_date: string | null }>;
  services: string[];
  contact: Record<string, string>;
  revenue_usd: number | null;
  total_funding_usd: number | null;
  report_text: string;
  sources_used: string[];
  validation_passed: boolean | null;
  relevancy_score: number | null;
  token_count_in: number | null;
  token_count_out: number | null;
  created_at: string;
}

export async function startResearch(name: string): Promise<StartResearchResponse> {
  const res = await fetch(`${API_BASE}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? "Failed to start research");
  }
  return res.json();
}

export async function fetchReport(reportId: string): Promise<Report> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}`);
  if (!res.ok) throw new Error("Report not found");
  return res.json();
}

export async function fetchReports(): Promise<{ reports: Partial<Report>[] }> {
  const res = await fetch(`${API_BASE}/api/reports`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  return res.json();
}

export function getStreamUrl(sessionId: string): string {
  return `${API_BASE}/api/research/${sessionId}/stream`;
}
