"use client";

import { useEffect, useState } from "react";
import { TriangleAlert, Bell, MapPin, CheckCircle2, Activity } from "lucide-react";
import { getEvents, usePoll, humanTime, type CareEvent } from "@/lib/careApi";

const CHART_FALLBACK = [40, 65, 50, 80, 60, 95, 72];
const DAYS_FALLBACK   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type DayCount = { day: string; count: number };
type DosesResponse = { days: DayCount[]; total: number };

type MockAlert = { icon: typeof Bell; tone: string; title: string; time: string };
const MOCK_ALERTS: MockAlert[] = [
  { icon: TriangleAlert, tone: "text-coral", title: "Ibuprofen low stock (4 left)", time: "12 min ago" },
  { icon: Bell, tone: "text-gold", title: "Amoxicillin expiring this month", time: "2 h ago" },
  { icon: CheckCircle2, tone: "text-emerald-600", title: "14:00 dose dispensed (Aspirin)", time: "today" },
  { icon: CheckCircle2, tone: "text-emerald-600", title: "Patrol completed, no anomalies", time: "today" },
];

function eventIcon(e: CareEvent) {
  const t = e.type.toLowerCase();
  if (t.includes("fall") || t.includes("emergency"))
    return { Icon: TriangleAlert, tone: "text-coral" };
  if (t.includes("expir") || t.includes("alert") || t.includes("health"))
    return { Icon: Bell, tone: "text-gold" };
  return { Icon: CheckCircle2, tone: "text-emerald-600" };
}

export default function ReportsPage() {
  const { data, online } = usePoll(getEvents, 5000);
  const live = online && Array.isArray(data);
  const liveEvents = live ? data!.slice(0, 12) : [];

  const [doses, setDoses] = useState<DosesResponse | null>(null);
  useEffect(() => {
    fetch("http://localhost:8000/doses/dispensed/last7days")
      .then((r) => r.json())
      .then(setDoses)
      .catch(() => {});
  }, []);

  const chartBars = doses
    ? (() => {
        const maxCount = Math.max(...doses.days.map((d) => d.count), 1);
        return doses.days.map((d) => ({
          day: d.day,
          height: Math.round((d.count / maxCount) * 100),
        }));
      })()
    : CHART_FALLBACK.map((h, i) => ({ day: DAYS_FALLBACK[i], height: h }));

  return (
    <div className="space-y-4 p-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        {/* chart */}
        <div className="rounded-2xl border border-hairline bg-paper p-5">
          <div className="mb-4 text-sm font-medium">Doses dispensed · last 7 days</div>
          <div className="flex h-36 items-end gap-3">
            {chartBars.map((bar, i) => (
              <span
                key={i}
                className="flex-1 rounded-t bg-harbour/70"
                style={{ height: `${bar.height}%` }}
              />
            ))}
          </div>
          <div className="mt-2 flex gap-3">
            {chartBars.map((bar, i) => (
              <span key={i} className="flex-1 text-center text-[11px] text-ink-soft">{bar.day}</span>
            ))}
          </div>
        </div>

        {/* alerts / live events */}
        <div className="rounded-2xl border border-hairline bg-paper p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm font-medium">
              <Activity size={15} /> {live ? "Live events" : "Alerts"}
            </span>
          </div>

          {live ? (
            <ul className="space-y-3">
              {liveEvents.length === 0 && (
                <li className="text-sm text-ink-soft">No events yet.</li>
              )}
              {liveEvents.map((e, i) => {
                const { Icon, tone } = eventIcon(e);
                return (
                  <li key={i} className="flex items-start gap-3">
                    <Icon size={16} className={`mt-0.5 ${tone}`} />
                    <span className="flex-1">
                      <span className="block text-sm">{e.message}</span>
                      <span className="text-[11px] text-ink-soft">
                        {e.type} · {humanTime(e.timestamp)}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <ul className="space-y-3">
              {MOCK_ALERTS.map((a, i) => (
                <li key={i} className="flex items-start gap-3">
                  <a.icon size={16} className={`mt-0.5 ${a.tone}`} />
                  <span className="flex-1">
                    <span className="block text-sm">{a.title}</span>
                    <span className="text-[11px] text-ink-soft">{a.time}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* emergency / nearest hospital */}
      <div className="flex items-center gap-4 rounded-2xl border border-hairline bg-paper p-5">
        <span className="grid h-11 w-11 flex-none place-items-center rounded-xl bg-coral/15 text-coral">
          <MapPin size={20} />
        </span>
        <div className="flex-1">
          <div className="text-sm font-medium">Emergency routing — Munich</div>
          <div className="text-[12px] text-ink-soft">
            Nearest: Klinikum rechts der Isar · 2.1 km · notifies 2 relatives + hospital with scene photo
          </div>
        </div>
        <button className="rounded-lg border border-hairline px-3 py-1.5 text-xs font-medium text-ink-soft hover:border-ink hover:text-ink">
          Configure
        </button>
      </div>
    </div>
  );
}
