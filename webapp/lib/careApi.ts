"use client";

// Client for the CareAI API server (ai/server/api_server.py, FastAPI).
// Point it at the AI machine via ngrok or LAN:
//   webapp/.env.local → NEXT_PUBLIC_CAREAI_URL=https://xxx.ngrok.app
//                    or NEXT_PUBLIC_CAREAI_URL=http://192.168.1.45:8000
// Defaults to localhost for same-machine dev. Pages fall back to their mock
// content when the API is unreachable.
import { useCallback, useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_CAREAI_URL || "http://localhost:8000";

export type CareMedicine = {
  name: string;
  expiration_date?: string;
  status?: string;
  scanned_at?: string;
};

export type CareEvent = {
  type: string;
  message: string;
  data?: unknown;
  timestamp: string;
};

export type CareSchedule = {
  id: string;
  medicine_name: string;
  dose?: string;
  times: string[];
  notes?: string;
  active?: boolean;
  created_at?: string;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 3000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        // ngrok free tier serves an HTML interstitial without this header
        "ngrok-skip-browser-warning": "true",
        ...init?.headers,
      },
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export const getMedicines = () => req<CareMedicine[]>("/medicines");
export const getEvents = () => req<CareEvent[]>("/events");
export const getScheduleList = () => req<CareSchedule[]>("/schedule");
export const addSchedule = (body: {
  medicine_name: string;
  dose: string;
  times: string[];
  notes?: string;
}) =>
  req<{ success: boolean; schedule: CareSchedule }>("/schedule", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const removeSchedule = (id: string) =>
  req<unknown>(`/schedule/${id}`, { method: "DELETE" });
export const askAssistant = (message: string) =>
  req<{ answer: string }>("/assistant/ask", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

/** Poll a CareAI endpoint; `online=false` → caller shows its mock fallback. */
export function usePoll<T>(fn: () => Promise<T>, ms = 8000) {
  const [data, setData] = useState<T | null>(null);
  const [online, setOnline] = useState(false);

  const refresh = useCallback(() => {
    fn()
      .then((d) => {
        setData(d);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, [fn]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, ms);
    return () => clearInterval(id);
  }, [refresh, ms]);

  return { data, online, refresh };
}
