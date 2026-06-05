import { TriangleAlert, Bell, MapPin, CheckCircle2 } from "lucide-react";

const STATS = [
  { label: "Doses on time (7d)", value: "98%", sub: "+3% vs last week" },
  { label: "Pick & place ops", value: "142", sub: "this week" },
  { label: "Avg response", value: "1.2s", sub: "emergency detect" },
  { label: "Uptime", value: "99.9%", sub: "30 days" },
];

const CHART = [40, 65, 50, 80, 60, 95, 72];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Alert = { icon: typeof Bell; tone: string; title: string; time: string };
const ALERTS: Alert[] = [
  { icon: TriangleAlert, tone: "text-coral", title: "Ibuprofen low stock (4 left)", time: "12 min ago" },
  { icon: Bell, tone: "text-gold", title: "Amoxicillin expiring this month", time: "2 h ago" },
  { icon: CheckCircle2, tone: "text-emerald-600", title: "14:00 dose dispensed — Aspirin", time: "today" },
  { icon: CheckCircle2, tone: "text-emerald-600", title: "Patrol completed, no anomalies", time: "today" },
];

export default function ReportsPage() {
  return (
    <div className="space-y-4 p-6">
      {/* stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="rounded-2xl border border-hairline bg-paper p-4">
            <div className="text-xs text-ink-soft">{s.label}</div>
            <div className="font-display mt-1 text-3xl font-extrabold tracking-tight">
              {s.value}
            </div>
            <div className="mt-1 text-[11px] text-ink-soft">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        {/* chart */}
        <div className="rounded-2xl border border-hairline bg-paper p-5">
          <div className="mb-4 text-sm font-medium">Doses dispensed · last 7 days</div>
          <div className="flex h-44 items-end gap-3">
            {CHART.map((h, i) => (
              <div key={i} className="flex flex-1 flex-col items-center gap-2">
                <span
                  className="w-full rounded-t bg-harbour/70"
                  style={{ height: `${h}%` }}
                />
                <span className="text-[11px] text-ink-soft">{DAYS[i]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* alerts */}
        <div className="rounded-2xl border border-hairline bg-paper p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium">Alerts</span>
            <span className="rounded-full bg-coral/15 px-2 py-0.5 text-[11px] font-medium text-coral">
              1 active
            </span>
          </div>
          <ul className="space-y-3">
            {ALERTS.map((a, i) => (
              <li key={i} className="flex items-start gap-3">
                <a.icon size={16} className={`mt-0.5 ${a.tone}`} />
                <span className="flex-1">
                  <span className="block text-sm">{a.title}</span>
                  <span className="text-[11px] text-ink-soft">{a.time}</span>
                </span>
              </li>
            ))}
          </ul>
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
