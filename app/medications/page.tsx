import { Plus } from "lucide-react";

type Med = {
  name: string;
  dose: string;
  stock: number; // 0..1
  count: string;
  expiry: string;
  status: "ok" | "soon" | "low";
};

const MEDS: Med[] = [
  { name: "Aspirin", dose: "100mg", stock: 0.8, count: "24 pills", expiry: "2027-03", status: "ok" },
  { name: "Metformin", dose: "500mg", stock: 0.45, count: "13 pills", expiry: "2026-11", status: "ok" },
  { name: "Vitamin D", dose: "1000 IU", stock: 0.6, count: "18 pills", expiry: "2026-09", status: "ok" },
  { name: "Ibuprofen", dose: "200mg", stock: 0.15, count: "4 pills", expiry: "2026-07", status: "low" },
  { name: "Amoxicillin", dose: "250mg", stock: 0.3, count: "9 pills", expiry: "2026-06", status: "soon" },
];

const STATUS: Record<Med["status"], { label: string; cls: string }> = {
  ok: { label: "In stock", cls: "bg-emerald-500/15 text-emerald-700" },
  soon: { label: "Expiring soon", cls: "bg-gold/20 text-gold" },
  low: { label: "Low stock", cls: "bg-coral/15 text-coral" },
};

export default function MedicationsPage() {
  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-ink-soft">Inventory · {MEDS.length} medications</p>
        <button className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-paper transition-colors hover:bg-ink/85">
          <Plus size={14} /> Add medication
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-hairline bg-paper">
        <div className="grid grid-cols-[1.5fr_1fr_2fr_1fr_1.2fr] border-b border-hairline bg-paper-2/40 px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-ink-soft">
          <span>Medication</span>
          <span>Dose</span>
          <span>Stock</span>
          <span>Expiry</span>
          <span>Status</span>
        </div>
        {MEDS.map((m) => (
          <div
            key={m.name}
            className="grid grid-cols-[1.5fr_1fr_2fr_1fr_1.2fr] items-center border-b border-hairline px-4 py-3.5 text-sm last:border-0"
          >
            <span className="font-medium">{m.name}</span>
            <span className="text-ink-soft">{m.dose}</span>
            <span className="flex items-center gap-2 pr-4">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper-2">
                <span
                  className={`block h-full rounded-full ${
                    m.status === "low" ? "bg-coral" : "bg-khaki"
                  }`}
                  style={{ width: `${m.stock * 100}%` }}
                />
              </span>
              <span className="w-14 text-right text-[11px] text-ink-soft">{m.count}</span>
            </span>
            <span className="font-mono text-[12px] text-ink-soft">{m.expiry}</span>
            <span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS[m.status].cls}`}
              >
                {STATUS[m.status].label}
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
