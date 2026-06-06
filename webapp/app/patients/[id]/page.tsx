"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Plus,
  Check,
  TriangleAlert,
  Pill,
  CalendarDays,
  StickyNote,
} from "lucide-react";
import { getPatient, type Prescription, type PatientEvent } from "@/lib/patients";
import { useRole, ROLE_LABELS } from "@/lib/role";
import {
  getScheduleList,
  getEvents,
  addSchedule as apiAddSchedule,
  removeSchedule as apiRemoveSchedule,
  usePoll,
  humanTime,
  type CareEvent,
} from "@/lib/careApi";

const EVENT_TONE: Record<PatientEvent["type"], string> = {
  medicine: "text-emerald-600",
  fall: "text-coral",
  alert: "text-gold",
  voice: "text-harbour",
  patrol: "text-ink-soft",
};

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { role, can } = useRole();
  const patient = getPatient(id);

  // beta: local state seeded from the mock roster
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(
    patient?.prescriptions ?? [],
  );
  const [events, setEvents] = useState<PatientEvent[]>(patient?.events ?? []);
  const [notes, setNotes] = useState<string[]>(patient?.notes ?? []);
  const [noteDraft, setNoteDraft] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [rx, setRx] = useState({ medicine_name: "", dose: "", times: "", notes: "" });

  // Live patient binds to the CareAI API (ngrok/LAN); mocks stay local.
  const isLive = patient?.status === "live";
  const sched = usePoll(getScheduleList, 8000);
  const evts = usePoll(getEvents, 6000);
  const liveMode = isLive && sched.online && Array.isArray(sched.data);

  if (!patient) {
    return <div className="p-6 text-sm text-ink-soft">Patient not found.</div>;
  }
  if (!can.managePatients) {
    return (
      <div className="p-6 text-sm text-ink-soft">
        Switch to the Nurse or Doctor role to view patients.
      </div>
    );
  }

  const addPrescription = async () => {
    if (!rx.medicine_name.trim() || !rx.times.trim()) return;
    const times = rx.times.split(",").map((t) => t.trim()).filter(Boolean);
    if (liveMode) {
      // doctor prescribes straight into CareAI on the AI machine
      try {
        await apiAddSchedule({
          medicine_name: rx.medicine_name.trim(),
          dose: rx.dose.trim(),
          times,
          notes: rx.notes.trim() || undefined,
        });
        sched.refresh();
      } catch {
        /* API hiccup: ignore, polling will resync */
      }
    } else {
      setPrescriptions((p) => [
        ...p,
        {
          id: `rx-${p.length + 1}-${rx.medicine_name}`,
          medicine_name: rx.medicine_name.trim(),
          dose: rx.dose.trim(),
          times,
          notes: rx.notes.trim() || undefined,
          active: true,
        },
      ]);
    }
    setRx({ medicine_name: "", dose: "", times: "", notes: "" });
    setShowForm(false);
  };

  const deactivate = async (rxId: string) => {
    if (liveMode) {
      try {
        await apiRemoveSchedule(rxId);
        sched.refresh();
      } catch {
        /* ignore */
      }
    } else {
      setPrescriptions((p) =>
        p.map((x) => (x.id === rxId ? { ...x, active: false } : x)),
      );
    }
  };

  // what we render: live CareAI schedule for the live patient, local otherwise
  const shownRx: Prescription[] = liveMode
    ? (sched.data ?? []).map((s) => ({
        id: s.id,
        medicine_name: s.medicine_name,
        dose: s.dose ?? "",
        times: s.times ?? [],
        notes: s.notes,
        active: s.active !== false,
      }))
    : prescriptions;

  const careEventType = (e: CareEvent): PatientEvent["type"] => {
    const t = e.type.toLowerCase();
    if (t.includes("fall") || t.includes("emergency")) return "fall";
    if (t.includes("voice")) return "voice";
    if (t.includes("medicine") || t.includes("scan")) return "medicine";
    if (t.includes("patrol")) return "patrol";
    return "alert";
  };

  const shownEvents: PatientEvent[] =
    isLive && evts.online && Array.isArray(evts.data)
      ? evts.data.slice(0, 10).map((e, i) => ({
          id: `live-${i}`,
          type: careEventType(e),
          message: e.message,
          time: humanTime(e.timestamp),
          acked: true, // live events come from CareAI; ack is local-only for mocks
        }))
      : events;

  const ack = (eventId: string) =>
    setEvents((e) => e.map((x) => (x.id === eventId ? { ...x, acked: true } : x)));

  const markDose = (p: Prescription) =>
    setEvents((e) => [
      {
        id: `e-${e.length + 1}`,
        type: "medicine",
        message: `Dose given (${p.medicine_name}) · by ${ROLE_LABELS[role]}`,
        time: "now",
      },
      ...e,
    ]);

  const addNote = () => {
    if (!noteDraft.trim()) return;
    setNotes((n) => [...n, `${noteDraft.trim()} (${ROLE_LABELS[role]})`]);
    setNoteDraft("");
  };

  return (
    <div className="space-y-5 p-6">
      {/* header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/patients"
            className="grid h-9 w-9 place-items-center rounded-lg border border-hairline text-ink-soft hover:text-ink"
            aria-label="Back to patients"
          >
            <ArrowLeft size={16} />
          </Link>
          <div>
            <h2 className="font-display text-xl font-bold tracking-tight">
              {patient.name}
            </h2>
            <p className="text-sm text-ink-soft">
              {patient.age} years · {patient.address}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* prescriptions */}
        <section className="rounded-2xl border border-hairline bg-paper p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-ink-soft">
              <CalendarDays size={15} /> Prescriptions
            </h3>
            {can.prescribe && (
              <button
                onClick={() => setShowForm((s) => !s)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-ink/85"
              >
                <Plus size={14} /> Prescribe
              </button>
            )}
          </div>

          {can.prescribe && showForm && (
            <div className="mb-4 space-y-2 rounded-xl border border-hairline bg-paper-2/40 p-3">
              <input
                value={rx.medicine_name}
                onChange={(e) => setRx({ ...rx, medicine_name: e.target.value })}
                placeholder="Medicine name"
                className="w-full rounded-lg border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
              />
              <div className="flex gap-2">
                <input
                  value={rx.dose}
                  onChange={(e) => setRx({ ...rx, dose: e.target.value })}
                  placeholder="Dose (e.g. 100mg · 1 pill)"
                  className="min-w-0 flex-1 rounded-lg border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
                />
                <input
                  value={rx.times}
                  onChange={(e) => setRx({ ...rx, times: e.target.value })}
                  placeholder="Times (08:00, 20:00)"
                  className="min-w-0 flex-1 rounded-lg border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
                />
              </div>
              <input
                value={rx.notes}
                onChange={(e) => setRx({ ...rx, notes: e.target.value })}
                placeholder="Notes (optional)"
                className="w-full rounded-lg border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
              />
              <button
                onClick={addPrescription}
                className="rounded-lg bg-harbour px-3 py-1.5 text-xs font-medium text-paper"
              >
                Add prescription
              </button>
            </div>
          )}

          <ul className="space-y-2">
            {shownRx.map((p) => (
              <li
                key={p.id}
                className={`rounded-xl border border-hairline px-3 py-2.5 ${
                  p.active ? "" : "opacity-45"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">
                    {p.medicine_name}{" "}
                    <span className="font-normal text-ink-soft">{p.dose}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    {p.times.map((t) => (
                      <span
                        key={t}
                        className="rounded bg-paper-2 px-1.5 py-0.5 font-mono text-[11px]"
                      >
                        {t}
                      </span>
                    ))}
                  </span>
                </div>
                {p.notes && (
                  <div className="mt-1 text-[12px] text-ink-soft">{p.notes}</div>
                )}
                <div className="mt-2 flex items-center gap-2">
                  {can.markDose && p.active && !liveMode && (
                    <button
                      onClick={() => markDose(p)}
                      className="inline-flex items-center gap-1 rounded-md border border-hairline px-2 py-1 text-[11px] text-ink-soft hover:border-ink hover:text-ink"
                    >
                      <Check size={12} /> Mark dose given
                    </button>
                  )}
                  {can.prescribe && p.active && (
                    <button
                      onClick={() => deactivate(p.id)}
                      className="rounded-md border border-hairline px-2 py-1 text-[11px] text-ink-soft hover:border-coral hover:text-coral"
                    >
                      Deactivate
                    </button>
                  )}
                  {!p.active && (
                    <span className="text-[11px] uppercase tracking-wider text-ink-soft">
                      Inactive
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {!can.prescribe && (
            <p className="mt-3 text-[11px] text-ink-soft">
              Nurses can mark doses given. Only doctors can prescribe.
            </p>
          )}
        </section>

        {/* medications inventory */}
        <section className="rounded-2xl border border-hairline bg-paper p-5">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-ink-soft">
            <Pill size={15} /> Medications
          </h3>
          <ul className="space-y-2">
            {patient.meds.map((m) => (
              <li
                key={m.name}
                className="flex items-center justify-between rounded-xl border border-hairline px-3 py-2.5 text-sm"
              >
                <span className="font-medium">
                  {m.name} <span className="font-normal text-ink-soft">{m.dose}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-ink-soft">
                    exp. {m.expiry}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      m.status === "ok"
                        ? "bg-emerald-500/15 text-emerald-700"
                        : m.status === "soon"
                          ? "bg-gold/20 text-gold"
                          : "bg-coral/15 text-coral"
                    }`}
                  >
                    {m.status === "ok" ? "OK" : m.status === "soon" ? "Expiring" : "Low"}
                  </span>
                </span>
              </li>
            ))}
          </ul>

          {/* events */}
          <h3 className="mb-3 mt-6 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-ink-soft">
            <TriangleAlert size={15} /> Recent events
          </h3>
          <ul className="space-y-2">
            {shownEvents.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-2 text-sm">
                <span>
                  <span className={`mr-1.5 font-medium ${EVENT_TONE[e.type]}`}>
                    {e.type}
                  </span>
                  {e.message}
                  <span className="ml-1.5 text-[11px] text-ink-soft">{e.time}</span>
                </span>
                {can.ackAlerts && (e.type === "alert" || e.type === "fall") && !e.acked && (
                  <button
                    onClick={() => ack(e.id)}
                    className="flex-none rounded-md border border-hairline px-2 py-0.5 text-[11px] text-ink-soft hover:border-ink hover:text-ink"
                  >
                    Ack
                  </button>
                )}
                {e.acked && !liveMode && (
                  <span className="flex-none text-[11px] text-emerald-700">acked</span>
                )}
              </li>
            ))}
          </ul>

          {/* notes */}
          <h3 className="mb-3 mt-6 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.15em] text-ink-soft">
            <StickyNote size={15} /> Care notes
          </h3>
          <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-ink-soft">
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
              placeholder="Add a note…"
              className="min-w-0 flex-1 rounded-lg border border-hairline bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
            />
            <button
              onClick={addNote}
              className="rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-paper"
            >
              Add
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
