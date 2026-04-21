"use client";
import { useState, useEffect, useRef } from "react";
import { getStreamUrl } from "@/lib/api";

export interface StreamEvent {
  stage: string;
  message: string;
  source?: string;
  status?: string;
  report_id?: string;
  relevancy_score?: number;
  passed?: boolean;
}

interface UseResearchStreamReturn {
  events: StreamEvent[];
  isComplete: boolean;
  isError: boolean;
  errorMsg: string | null;
  reportId: string | null;
}

export function useResearchStream(sessionId: string | null): UseResearchStreamReturn {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [isError, setIsError] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const es = new EventSource(getStreamUrl(sessionId));
    esRef.current = es;

    es.addEventListener("progress", (e) => {
      const data: StreamEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, data]);
    });

    es.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev, { stage: "complete", message: "Research complete!", ...data }]);
      if (data.report_id) setReportId(data.report_id);
      setIsComplete(true);
      es.close();
    });

    es.addEventListener("error", (e) => {
      const data = (e as MessageEvent).data
        ? JSON.parse((e as MessageEvent).data)
        : { message: "Stream connection lost." };
      setErrorMsg(data.message ?? "Unknown error");
      setIsError(true);
      es.close();
    });

    return () => {
      es.close();
    };
  }, [sessionId]);

  return { events, isComplete, isError, errorMsg, reportId };
}
