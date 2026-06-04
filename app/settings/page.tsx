function Toggle({ on }: { on: boolean }) {
  return (
    <span
      className={`flex h-6 w-11 items-center rounded-full p-0.5 transition-colors ${
        on ? "bg-ink" : "bg-hairline"
      }`}
    >
      <span
        className={`h-5 w-5 rounded-full bg-paper shadow transition-transform ${
          on ? "translate-x-5" : ""
        }`}
      />
    </span>
  );
}

const ROWS: { group: string; items: { label: string; hint: string; on: boolean }[] }[] = [
  {
    group: "Robot",
    items: [
      { label: "Safe mode", hint: "Limit joint speed & torque", on: true },
      { label: "Auto-patrol", hint: "Hourly room scan", on: true },
      { label: "Collision guard", hint: "Stop on unexpected contact", on: true },
    ],
  },
  {
    group: "Notifications",
    items: [
      { label: "Email alerts (Gmail)", hint: "Send alerts to your inbox", on: true },
      { label: "Notify relatives", hint: "On emergencies", on: true },
      { label: "Low-stock reminders", hint: "When a med drops below 20%", on: false },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {ROWS.map((section) => (
        <div key={section.group}>
          <h2 className="font-display mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-ink-soft">
            {section.group}
          </h2>
          <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
            {section.items.map((it) => (
              <div
                key={it.label}
                className="flex items-center justify-between border-b border-hairline px-4 py-3.5 last:border-0"
              >
                <span>
                  <span className="block text-sm font-medium">{it.label}</span>
                  <span className="text-[12px] text-ink-soft">{it.hint}</span>
                </span>
                <Toggle on={it.on} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
