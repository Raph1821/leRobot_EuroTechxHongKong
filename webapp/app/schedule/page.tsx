"use client";

import { useEffect, useState } from "react";

const API = "http://localhost:8000";
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const FALLBACK_HOURS = ["08:00", "12:00", "14:00", "18:00", "22:00"];
const COLORS = [
  "var(--harbour)",
  "var(--coral)",
  "var(--gold)",
  "var(--khaki)",
];

type Schedule = {
  id: string;
  medicine_name: string;
  dose: string;
  times: string[];
  notes: string;
  active: boolean;
  created_at: string;
};

function weekRange(): string {
  const now = new Date();
  const mon = new Date(now);
  mon.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
  return `${fmt(mon)} – ${fmt(sun)}, ${sun.getFullYear()}`;
}

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    fetch(`${API}/schedule`)
      .then((r) => r.json())
      .then((data) => { setSchedules(data); setOffline(false); })
      .catch(() => setOffline(true))
      .finally(() => setLoading(false));
  }, []);

  // Build sorted unique hour rows from real data; fall back to static list
  const hours = schedules.length > 0
    ? [...new Set(schedules.flatMap((s) => s.times))].sort()
    : FALLBACK_HOURS;

  // Map each schedule to a colour
  const colorOf = (id: string) => COLORS[schedules.findIndex((s) => s.id === id) % COLORS.length];

  // For a given (hour, day) cell: find the schedule that has that time
  // (daily recurring → same pill in every day column)
  const doseAt = (hour: string) =>
    schedules.find((s) => s.times.includes(hour));

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-ink-soft">Prescription schedule · this week</p>
        <span className="rounded-full border border-hairline px-3 py-1 text-xs text-ink-soft">
          {offline ? "backend offline" : weekRange()}
        </span>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
        {/* day header */}
        <div className="grid grid-cols-[64px_repeat(7,1fr)] border-b border-hairline bg-paper-2/40 text-xs font-medium text-ink-soft">
          <div className="px-3 py-2.5" />
          {DAYS.map((d) => (
            <div key={d} className="px-3 py-2.5 text-center">{d}</div>
          ))}
        </div>

        {loading && (
          <div className="px-4 py-8 text-center text-sm text-ink-soft">Loading…</div>
        )}

        {!loading && hours.map((h, hi) => {
          const dose = doseAt(h);
          return (
            <div
              key={h}
              className="grid grid-cols-[64px_repeat(7,1fr)] border-b border-hairline last:border-0"
            >
              <div className="px-3 py-3 font-mono text-[11px] text-ink-soft">{h}</div>
              {DAYS.map((_, di) => (
                <div key={di} className="border-l border-hairline px-1.5 py-1.5">
                  {dose && (
                    <span
                      className="block truncate rounded-md px-2 py-1 text-[11px] font-medium text-paper"
                      style={{ backgroundColor: colorOf(dose.id) }}
                    >
                      {dose.medicine_name}
                    </span>
                  )}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
