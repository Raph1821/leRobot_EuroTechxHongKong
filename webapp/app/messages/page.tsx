"use client";

import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { PATIENTS } from "@/lib/patients";
import { useRole, ROLE_LABELS, type Role } from "@/lib/role";

type Msg = { from: Role; text: string; time: string };

const LIVE_PATIENT_ID = PATIENTS[0].id;

const ROLE_TONE: Record<Role, string> = {
  patient: "bg-coral/12 text-ink",
  nurse: "bg-gold/15 text-ink",
  doctor: "bg-harbour/10 text-ink",
};

const SEED: Msg[] = [
  { from: "nurse", text: "Good morning! Elda dispensed the 08:00 dose, all good.", time: "08:05" },
  { from: "patient", text: "Thank you. Feeling a bit tired today.", time: "09:12" },
  { from: "doctor", text: "Noted. Let's keep an eye on it, I'll check your schedule.", time: "09:30" },
];

function loadThread(patientId: string): Msg[] {
  try {
    const raw = localStorage.getItem(`elda-chat-${patientId}`);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return SEED;
}

function saveThread(patientId: string, msgs: Msg[]) {
  try {
    localStorage.setItem(`elda-chat-${patientId}`, JSON.stringify(msgs));
  } catch {
    /* ignore */
  }
}

export default function MessagesPage() {
  const { role, can } = useRole();
  const [patientId, setPatientId] = useState(LIVE_PATIENT_ID);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // patient role only sees their own thread
  const activeId = can.managePatients ? patientId : LIVE_PATIENT_ID;

  useEffect(() => {
    setMessages(loadThread(activeId));
  }, [activeId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    const next = [...messages, { from: role, text, time }];
    setMessages(next);
    saveThread(activeId, next);
    setDraft("");
  };

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[260px_1fr]">
      {/* threads (care team only) */}
      {can.managePatients && (
        <aside className="hidden border-r border-hairline bg-paper-2/30 p-3 lg:block">
          <p className="mb-2 px-2 text-[11px] uppercase tracking-[0.15em] text-ink-soft">
            Conversations
          </p>
          {PATIENTS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPatientId(p.id)}
              className={`mb-1 w-full rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                activeId === p.id ? "bg-ink text-paper" : "hover:bg-paper-2"
              }`}
            >
              <span className="block font-medium">{p.name}</span>
              <span
                className={`text-[11px] ${activeId === p.id ? "text-paper/70" : "text-ink-soft"}`}
              >
                {p.age} years
              </span>
            </button>
          ))}
        </aside>
      )}

      {/* conversation */}
      <div className="flex min-h-0 flex-col">
        <div className="border-b border-hairline px-5 py-3 text-sm text-ink-soft">
          {can.managePatients
            ? `Thread · ${PATIENTS.find((p) => p.id === activeId)?.name}`
            : "Your care team"}
          <span className="ml-2 rounded-full bg-paper-2 px-2 py-0.5 text-[11px]">
            you are {ROLE_LABELS[role]}
          </span>
        </div>

        <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-5">
          {messages.map((m, i) => {
            const own = m.from === role;
            return (
              <div key={i} className={`flex ${own ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    own ? "bg-ink text-paper" : `border border-hairline ${ROLE_TONE[m.from]}`
                  }`}
                >
                  {!own && (
                    <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-soft">
                      {ROLE_LABELS[m.from]}
                    </div>
                  )}
                  {m.text}
                  <div
                    className={`mt-1 text-right text-[10px] ${own ? "text-paper/60" : "text-ink-soft"}`}
                  >
                    {m.time}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-center gap-2 border-t border-hairline p-3"
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Message as ${ROLE_LABELS[role]}…`}
            className="min-w-0 flex-1 rounded-xl border border-hairline bg-paper px-3 py-2.5 text-sm outline-none focus:border-ink"
          />
          <button
            type="submit"
            disabled={!draft.trim()}
            aria-label="Send"
            className="grid h-10 w-10 flex-none place-items-center rounded-xl bg-ink text-paper disabled:opacity-30"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
