"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { PATIENTS } from "@/lib/patients";
import { useRole, ROLE_LABELS } from "@/lib/role";

const STATUS_CHIP: Record<string, { label: string; cls: string }> = {
  live: { label: "Live · Elda connected", cls: "bg-emerald-500/15 text-emerald-700" },
  stable: { label: "Stable", cls: "bg-paper-2 text-ink-soft" },
  attention: { label: "Needs attention", cls: "bg-coral/15 text-coral" },
};

export default function PatientsPage() {
  const { role, can } = useRole();

  if (!can.managePatients) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <p className="font-display text-xl font-bold">Care team space</p>
          <p className="mt-2 text-sm text-ink-soft">
            Switch to the Nurse or Doctor role to manage patients.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <p className="mb-5 text-sm text-ink-soft">
        {PATIENTS.length} patients · signed in as {ROLE_LABELS[role]}
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PATIENTS.map((p) => {
          const chip = STATUS_CHIP[p.status];
          const activeAlerts = p.events.filter(
            (e) => (e.type === "alert" || e.type === "fall") && !e.acked,
          ).length;
          return (
            <Link
              key={p.id}
              href={`/patients/${p.id}`}
              className="group rounded-2xl border border-hairline bg-paper p-5 transition-all hover:-translate-y-0.5 hover:border-ink/30 hover:shadow-[0_12px_40px_-20px_rgba(14,17,22,0.4)]"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-display text-lg font-bold tracking-tight">
                    {p.name}
                  </div>
                  <div className="mt-0.5 text-sm text-ink-soft">
                    {p.age} years · {p.address}
                  </div>
                </div>
                <ChevronRight
                  size={18}
                  className="mt-1 text-ink-soft transition-transform group-hover:translate-x-0.5"
                />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {p.status !== "live" && (
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${chip.cls}`}
                  >
                    {chip.label}
                  </span>
                )}
                {activeAlerts > 0 && (
                  <span className="rounded-full bg-coral/15 px-2.5 py-0.5 text-[11px] font-medium text-coral">
                    {activeAlerts} alert{activeAlerts > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <div className="mt-3 text-[12px] text-ink-soft">
                {p.prescriptions.filter((rx) => rx.active).length} active prescription
                {p.prescriptions.filter((rx) => rx.active).length !== 1 ? "s" : ""} ·{" "}
                {p.meds.length} medications
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
