"use client";

import { useEffect, useState } from "react";
import { Clock, Pill } from "lucide-react";

const API = "http://localhost:8000";

type Schedule = {
  id: string;
  medicine_name: string;
  dose: string;
  times: string[];
  notes: string;
  active: boolean;
  created_at: string;
};

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/schedule`)
      .then((r) => r.json())
      .then((data) => {
        setSchedules(data);
        setOffline(false);
      })
      .catch(() => setOffline(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-ink-soft">Medicine schedule · daily recurring</p>
        {offline && (
          <span className="rounded-full border border-hairline px-3 py-1 text-xs text-ink-soft">
            backend offline
          </span>
        )}
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
        {/* header */}
        <div className="grid grid-cols-[1fr_120px_160px] border-b border-hairline bg-paper-2/40 px-4 py-2.5 text-xs font-medium text-ink-soft">
          <span>Medicine</span>
          <span>Dose</span>
          <span>Daily times</span>
        </div>

        {loading && (
          <div className="px-4 py-8 text-center text-sm text-ink-soft">Loading…</div>
        )}

        {!loading && (offline || schedules.length === 0) && (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <Pill size={28} strokeWidth={1.5} className="text-ink/20" />
            <p className="text-sm text-ink-soft">
              {offline ? "Could not reach the CareAI backend." : "No active medicine schedules."}
            </p>
            {offline && (
              <p className="text-xs text-ink-soft/60">
                Start the server: <code className="font-mono">uvicorn ai.server.api_server:app --port 8000</code>
              </p>
            )}
          </div>
        )}

        {!loading && !offline && schedules.map((s, i) => (
          <div
            key={s.id}
            className={`grid grid-cols-[1fr_120px_160px] items-center px-4 py-3 ${
              i < schedules.length - 1 ? "border-b border-hairline" : ""
            }`}
          >
            <div>
              <p className="text-sm font-medium capitalize">{s.medicine_name}</p>
              {s.notes && (
                <p className="mt-0.5 text-[11px] text-ink-soft">{s.notes}</p>
              )}
            </div>
            <span className="text-sm text-ink-soft">{s.dose}</span>
            <div className="flex flex-wrap gap-1.5">
              {s.times.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 rounded-full bg-gold/15 px-2 py-0.5 font-mono text-[11px] font-medium text-gold"
                >
                  <Clock size={10} />
                  {t}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
