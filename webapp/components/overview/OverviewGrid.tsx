"use client";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import RGL, { type Layout } from "react-grid-layout";
import {
  Bot,
  Video,
  CalendarDays,
  Clock,
  Pill,
  Activity,
  TriangleAlert,
  GripVertical,
  MessageCircle,
  MessageSquare,
  Siren,
  Mic,
  MapPin,
  type LucideIcon,
} from "lucide-react";
import { JOINTS, radToDeg } from "@/lib/joints";
import { useCameraLive } from "@/lib/useCameraLive";
import { useJoints } from "@/lib/jointStore";
import { ROLE_LABELS, useRole, type Role } from "@/lib/role";
import { PATIENTS } from "@/lib/patients";

// RGL's shipped types diverge from @types; pin exactly the props we use.
type GridProps = {
  width: number;
  layout: Layout;
  cols: number;
  rowHeight: number;
  margin: [number, number];
  containerPadding: [number, number];
  draggableHandle: string;
  isBounded?: boolean;
  className?: string;
  onLayoutChange: (layout: Layout) => void;
  onDragStart?: () => void;
  onDragStop?: () => void;
  onResizeStart?: () => void;
  onResizeStop?: () => void;
  children: React.ReactNode;
};
const GridLayout = RGL as unknown as React.ComponentType<GridProps>;

function JointChips() {
  const { values } = useJoints();
  return (
    <div className="grid grid-cols-3 gap-2 font-mono text-[11px] text-ink-soft">
      {JOINTS.map((j) => (
        <span key={j.name} className="rounded-md bg-paper-2 px-2 py-1 text-center">
          {j.label.split(" ")[0].toLowerCase()} {radToDeg(values[j.name] ?? 0).toFixed(0)}°
        </span>
      ))}
    </div>
  );
}

// live mini 3D preview of the SO-101 inside the widget
const RobotMiniViewer = dynamic(() => import("@/components/RobotMiniViewer"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center font-display text-5xl font-extrabold tracking-tight text-ink/15">
      SO-101
    </div>
  ),
});

function CameraBody() {
  const { live, streamKey, STREAM_URL } = useCameraLive();
  return (
    <div className="relative h-full min-h-[80px] overflow-hidden rounded-xl bg-ink">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        key={streamKey}
        src={STREAM_URL}
        alt="Camera preview"
        className="h-full w-full object-cover"
      />
      {!live && (
        <div className="absolute inset-0 bg-ink bg-[radial-gradient(circle_at_50%_40%,rgba(255,255,255,0.08),transparent_60%)]" />
      )}
      <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-black/40 px-2 py-0.5 text-[10px] font-medium text-paper">
        <span
          className={`h-1.5 w-1.5 rounded-full ${live ? "bg-coral" : "bg-paper/40"}`}
        />
        {live ? "LIVE" : "OFFLINE"}
      </span>
    </div>
  );
}

type NextDose = { has_next: false } | { has_next: true; medicine_name: string; dose: string; time: string; notes: string };

function minutesUntil(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  const now = new Date();
  const target = new Date();
  target.setHours(h, m, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  return Math.round((target.getTime() - now.getTime()) / 60000);
}

function formatCountdown(mins: number): string {
  if (mins < 60) return `in ${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `in ${h}h` : `in ${h}h ${m}m`;
}

function NextDoseBody() {
  const [data, setData] = useState<NextDose | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/schedule/next")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ has_next: false }));
  }, []);

  if (!data) {
    return (
      <div className="flex h-full items-center">
        <span className="text-sm text-ink-soft">Loading…</span>
      </div>
    );
  }

  if (!data.has_next) {
    return (
      <div className="flex h-full flex-col justify-center">
        <Clock size={20} strokeWidth={1.5} className="mb-1 text-ink/25" />
        <span className="text-sm text-ink-soft">No doses scheduled</span>
      </div>
    );
  }

  const mins = minutesUntil(data.time);
  return (
    <div className="flex h-full flex-col justify-center">
      <span className="font-display text-3xl font-extrabold tracking-tight">{data.time}</span>
      <span className="mt-1 text-sm text-ink-soft capitalize">
        {data.medicine_name} · {data.dose}
      </span>
      <span className="mt-2 inline-flex w-fit rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-medium text-gold">
        {formatCountdown(mins)}
      </span>
    </div>
  );
}

function ControlBody() {
  const { armValues } = useJoints();
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl bg-paper-2/60">
        <div className="absolute inset-0">
          <RobotMiniViewer jointValues={armValues} />
        </div>
      </div>
      <JointChips />
    </div>
  );
}

// teaser for the Elda voice/text assistant
function InteractionBody() {
  return (
    <div className="flex h-full items-center gap-3">
      <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-harbour/10 text-harbour">
        <Mic size={18} />
      </span>
      <div className="min-w-0">
        <div className="text-sm font-medium">Ask Elda anything</div>
        <div className="truncate text-[12px] text-ink-soft">
          &ldquo;What medicines do I take today?&rdquo;
        </div>
      </div>
    </div>
  );
}

// last message of the care-team thread (shared with /messages via localStorage)
function MessagesBody() {
  const [last, setLast] = useState<{ from: Role; text: string; time: string } | null>(null);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(`elda-chat-${PATIENTS[0].id}`);
      if (raw) {
        const msgs = JSON.parse(raw);
        if (Array.isArray(msgs) && msgs.length) {
          setLast(msgs[msgs.length - 1]);
          return;
        }
      }
    } catch {
      /* ignore */
    }
    setLast({
      from: "doctor",
      text: "Noted. Let's keep an eye on it, I'll check your schedule.",
      time: "09:30",
    });
  }, []);

  return (
    <div className="flex h-full flex-col justify-center">
      {last ? (
        <>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft">
            {ROLE_LABELS[last.from] ?? last.from} · {last.time}
          </div>
          <div className="mt-1 line-clamp-2 text-sm">{last.text}</div>
        </>
      ) : (
        <div className="text-sm text-ink-soft">No messages yet.</div>
      )}
    </div>
  );
}

function EmergencyBody() {
  return (
    <div className="flex h-full items-center gap-3">
      <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-coral/12 text-coral">
        <Siren size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">All clear</div>
        <div className="flex items-center gap-1 truncate text-[12px] text-ink-soft">
          <MapPin size={11} /> Nearest hospital 0.4 km
        </div>
      </div>
    </div>
  );
}

type Card = {
  id: string;
  href: string;
  title: string;
  Icon: LucideIcon;
  accent: string;
  body: ReactNode;
};

const CARDS: Card[] = [
  {
    id: "control",
    href: "/control",
    title: "Manual Control",
    Icon: Bot,
    accent: "var(--coral)",
    body: <ControlBody />,
  },
  {
    id: "camera",
    href: "/camera",
    title: "Camera",
    Icon: Video,
    accent: "var(--harbour)",
    body: <CameraBody />,
  },
  {
    id: "dose",
    href: "/schedule",
    title: "Next Dose",
    Icon: CalendarDays,
    accent: "var(--gold)",
    body: <NextDoseBody />,
  },
  {
    id: "meds",
    href: "/medications",
    title: "Medications",
    Icon: Pill,
    accent: "var(--khaki)",
    body: (
      <div className="flex h-full flex-col justify-center gap-2 text-sm">
        {[
          { n: "Aspirin", s: 0.8, d: "OK" },
          { n: "Metformin", s: 0.45, d: "OK" },
          { n: "Ibuprofen", s: 0.15, d: "Exp. soon" },
        ].map((m) => (
          <div key={m.n} className="flex items-center gap-2">
            <span className="w-20 truncate text-ink">{m.n}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper-2">
              <span
                className="block h-full rounded-full bg-khaki"
                style={{ width: `${m.s * 100}%` }}
              />
            </span>
            <span className="w-16 text-right text-[11px] text-ink-soft">{m.d}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    id: "reports",
    href: "/reports",
    title: "Reports & Alerts",
    Icon: Activity,
    accent: "var(--ink)",
    body: (
      <div className="flex h-full items-stretch gap-4">
        <div className="flex flex-col justify-center">
          <span className="font-display text-3xl font-extrabold tracking-tight">98%</span>
          <span className="text-xs text-ink-soft">doses on time (7d)</span>
        </div>
        <div className="flex flex-1 items-end gap-1.5">
          {[40, 65, 50, 80, 60, 95, 70].map((h, i) => (
            <span key={i} className="flex-1 rounded-t bg-harbour/70" style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="flex w-36 flex-col justify-center gap-1.5 border-l border-hairline pl-3 text-[11px]">
          <span className="flex items-center gap-1.5 text-coral">
            <TriangleAlert size={12} /> 1 active alert
          </span>
          <span className="text-ink-soft">Ibuprofen low stock</span>
        </div>
      </div>
    ),
  },
  {
    id: "interaction",
    href: "/interaction",
    title: "Interaction",
    Icon: MessageCircle,
    accent: "var(--harbour)",
    body: <InteractionBody />,
  },
  {
    id: "messages",
    href: "/messages",
    title: "Messages",
    Icon: MessageSquare,
    accent: "var(--gold)",
    body: <MessagesBody />,
  },
  {
    id: "emergency",
    href: "/emergency",
    title: "Emergency",
    Icon: Siren,
    accent: "var(--coral)",
    body: <EmergencyBody />,
  },
];

const byId = (id: string) => CARDS.find((c) => c.id === id)!;

// patients don't get the arm-control widget; care team does
const PATIENT_DEFAULT_LAYOUT: Layout = [
  { i: "camera", x: 0, y: 0, w: 5, h: 2, minW: 2, minH: 2 },
  { i: "dose", x: 5, y: 0, w: 3, h: 1, minW: 3, minH: 1 },
  { i: "reports", x: 8, y: 0, w: 4, h: 1, minW: 4, minH: 1 },
  { i: "messages", x: 5, y: 1, w: 4, h: 1, minW: 2, minH: 1 },
  { i: "interaction", x: 9, y: 1, w: 3, h: 1, minW: 2, minH: 1 },
  { i: "meds", x: 0, y: 2, w: 7, h: 2, minW: 2, minH: 2 },
  { i: "emergency", x: 7, y: 2, w: 5, h: 1, minW: 2, minH: 1 },
];

const CARE_DEFAULT_LAYOUT: Layout = [
  { i: "control", x: 0, y: 0, w: 6, h: 2, minW: 3, minH: 2 },
  { i: "camera", x: 6, y: 0, w: 6, h: 2, minW: 2, minH: 2 },
  { i: "meds", x: 0, y: 2, w: 5, h: 2, minW: 2, minH: 2 },
  { i: "dose", x: 5, y: 2, w: 3, h: 1, minW: 3, minH: 1 },
  { i: "reports", x: 8, y: 2, w: 4, h: 1, minW: 4, minH: 1 },
  { i: "interaction", x: 5, y: 3, w: 3, h: 1, minW: 2, minH: 1 },
  { i: "messages", x: 8, y: 3, w: 4, h: 1, minW: 2, minH: 1 },
  { i: "emergency", x: 0, y: 4, w: 5, h: 1, minW: 2, minH: 1 },
];

function Widget({
  card,
  interacting,
}: {
  card: Card;
  interacting: React.RefObject<boolean>;
}) {
  const router = useRouter();
  return (
    <div
      role="link"
      aria-label={`Open ${card.title}`}
      onClick={(e) => {
        // a drag/resize (or a click on the grip) is not a navigation
        if (interacting.current) return;
        if ((e.target as HTMLElement).closest(".widget-drag")) return;
        router.push(card.href);
      }}
      className="flex h-full cursor-pointer flex-col overflow-hidden rounded-2xl border border-hairline bg-paper p-5 transition-colors hover:border-ink/30"
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="flex items-center gap-2.5">
          <span
            className="grid h-8 w-8 place-items-center rounded-lg text-paper"
            style={{ backgroundColor: card.accent }}
          >
            <card.Icon size={16} strokeWidth={2} />
          </span>
          <span className="font-display text-sm font-semibold tracking-tight">
            {card.title}
          </span>
        </span>
        <button
          aria-label="Drag to move"
          className="widget-drag cursor-grab touch-none rounded-md p-1 text-ink-soft/50 hover:text-ink active:cursor-grabbing"
        >
          <GripVertical size={15} />
        </button>
      </div>
      <div className="min-h-0 flex-1">{card.body}</div>
    </div>
  );
}

export default function OverviewGrid() {
  const ref = useRef<HTMLDivElement>(null);
  const { role } = useRole();
  const [width, setWidth] = useState(0);
  // true while a widget is being dragged/resized — suppresses the click-to-open
  const interacting = useRef(false);
  const beginInteract = () => {
    interacting.current = true;
  };
  const endInteract = () => {
    // the click event fires right after mouseup; release on the next tick
    setTimeout(() => {
      interacting.current = false;
    }, 0);
  };

  const cards = role === "patient" ? CARDS.filter((c) => c.id !== "control") : CARDS;
  const defaultLayout = role === "patient" ? PATIENT_DEFAULT_LAYOUT : CARE_DEFAULT_LAYOUT;
  const storageKey = `overview-layout-v7-${role}`;

  const [layout, setLayout] = useState<Layout>(defaultLayout);

  // restore saved layout (per role)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed: Layout = JSON.parse(saved);
        const valid = parsed.filter((l) => cards.some((c) => c.id === l.i));
        if (valid.length === cards.length) {
          setLayout(valid);
          return;
        }
      }
    } catch {
      /* ignore */
    }
    setLayout(defaultLayout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  // measure container width (WidthProvider isn't exported from RGL's ESM build)
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const onLayoutChange = (next: Layout) => {
    setLayout(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  return (
    <div ref={ref} className="p-4">
      {width > 0 && (
        <GridLayout
          width={width}
          className="layout"
          layout={layout}
          cols={12}
          rowHeight={72}
          margin={[16, 16]}
          containerPadding={[8, 8]}
          draggableHandle=".widget-drag"
          onLayoutChange={onLayoutChange}
          onDragStart={beginInteract}
          onDragStop={endInteract}
          onResizeStart={beginInteract}
          onResizeStop={endInteract}
          isBounded
        >
          {layout.map((l) => (
            <div key={l.i}>
              <Widget card={byId(l.i)} interacting={interacting} />
            </div>
          ))}
        </GridLayout>
      )}
    </div>
  );
}
