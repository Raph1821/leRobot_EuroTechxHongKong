const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = ["08:00", "12:00", "14:00", "18:00", "22:00"];

type Dose = { day: number; hour: number; name: string; color: string };
const DOSES: Dose[] = [
  { day: 0, hour: 0, name: "Metformin", color: "var(--harbour)" },
  { day: 0, hour: 2, name: "Aspirin", color: "var(--coral)" },
  { day: 1, hour: 2, name: "Aspirin", color: "var(--coral)" },
  { day: 2, hour: 1, name: "Vitamin D", color: "var(--gold)" },
  { day: 2, hour: 4, name: "Metformin", color: "var(--harbour)" },
  { day: 3, hour: 2, name: "Aspirin", color: "var(--coral)" },
  { day: 4, hour: 0, name: "Metformin", color: "var(--harbour)" },
  { day: 5, hour: 3, name: "Ibuprofen", color: "var(--khaki)" },
  { day: 6, hour: 2, name: "Aspirin", color: "var(--coral)" },
];

export default function SchedulePage() {
  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-ink-soft">Prescription schedule · this week</p>
        <span className="rounded-full border border-hairline px-3 py-1 text-xs text-ink-soft">
          June 1 – 7, 2026
        </span>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
        <div className="grid grid-cols-[64px_repeat(7,1fr)] border-b border-hairline bg-paper-2/40 text-xs font-medium text-ink-soft">
          <div className="px-3 py-2.5" />
          {DAYS.map((d) => (
            <div key={d} className="px-3 py-2.5 text-center">
              {d}
            </div>
          ))}
        </div>
        {HOURS.map((h, hi) => (
          <div
            key={h}
            className="grid grid-cols-[64px_repeat(7,1fr)] border-b border-hairline last:border-0"
          >
            <div className="px-3 py-3 font-mono text-[11px] text-ink-soft">{h}</div>
            {DAYS.map((_, di) => {
              const dose = DOSES.find((x) => x.day === di && x.hour === hi);
              return (
                <div
                  key={di}
                  className="border-l border-hairline px-1.5 py-1.5"
                >
                  {dose && (
                    <span
                      className="block truncate rounded-md px-2 py-1 text-[11px] font-medium text-paper"
                      style={{ backgroundColor: dose.color }}
                    >
                      {dose.name}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
