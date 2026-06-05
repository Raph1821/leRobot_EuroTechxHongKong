"use client";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import RGL, { type Layout } from "react-grid-layout";
import {
  Bot,
  Video,
  CalendarDays,
  Pill,
  Activity,
  TriangleAlert,
  GripVertical,
  ArrowUpRight,
  type LucideIcon,
} from "lucide-react";
import { JOINTS, radToDeg } from "@/lib/joints";
import { useJoints } from "@/lib/jointStore";

const STORAGE_KEY = "overview-layout-v5";

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

function ControlBody() {
  const { values } = useJoints();
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl bg-paper-2/60">
        <div className="absolute inset-0">
          <RobotMiniViewer jointValues={values} />
        </div>
      </div>
      <JointChips />
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
    body: (
      <div className="relative h-full min-h-[80px] overflow-hidden rounded-xl bg-ink">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(255,255,255,0.08),transparent_60%)]" />
        <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-black/40 px-2 py-0.5 text-[10px] font-medium text-paper">
          <span className="h-1.5 w-1.5 rounded-full bg-coral" /> LIVE
        </span>
        <span className="absolute bottom-2 right-2 font-mono text-[10px] text-paper/60">
          14:02:31
        </span>
      </div>
    ),
  },
  {
    id: "dose",
    href: "/schedule",
    title: "Next Dose",
    Icon: CalendarDays,
    accent: "var(--gold)",
    body: (
      <div className="flex h-full flex-col justify-center">
        <span className="font-display text-3xl font-extrabold tracking-tight">14:00</span>
        <span className="mt-1 text-sm text-ink-soft">Aspirin · 100mg · 1 pill</span>
        <span className="mt-2 inline-flex w-fit rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-medium text-gold">
          in 58 min
        </span>
      </div>
    ),
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
];

const byId = (id: string) => CARDS.find((c) => c.id === id)!;

const DEFAULT_LAYOUT: Layout = [
  { i: "control", x: 0, y: 0, w: 6, h: 2, minW: 3, minH: 2 },
  { i: "camera", x: 6, y: 0, w: 6, h: 2, minW: 2, minH: 2 },
  { i: "meds", x: 0, y: 2, w: 5, h: 2, minW: 2, minH: 2 },
  { i: "dose", x: 5, y: 2, w: 3, h: 1, minW: 3, minH: 1 },
  { i: "reports", x: 8, y: 2, w: 4, h: 1, minW: 4, minH: 1 },
];

function Widget({ card }: { card: Card }) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-hairline bg-paper p-5">
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
        <span className="flex items-center gap-1">
          <button
            aria-label="Drag to move"
            className="widget-drag cursor-grab touch-none rounded-md p-1 text-ink-soft/50 hover:text-ink active:cursor-grabbing"
          >
            <GripVertical size={15} />
          </button>
          <Link
            href={card.href}
            aria-label={`Open ${card.title}`}
            className="rounded-md p-1 text-ink-soft transition-colors hover:bg-paper-2 hover:text-ink"
          >
            <ArrowUpRight size={16} />
          </Link>
        </span>
      </div>
      <div className="min-h-0 flex-1">{card.body}</div>
    </div>
  );
}

export default function OverviewGrid() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);

  // restore saved layout
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed: Layout = JSON.parse(saved);
        const valid = parsed.filter((l) => CARDS.some((c) => c.id === l.i));
        if (valid.length === CARDS.length) setLayout(valid);
      }
    } catch {
      /* ignore */
    }
  }, []);

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
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
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
          isBounded
        >
          {layout.map((l) => (
            <div key={l.i}>
              <Widget card={byId(l.i)} />
            </div>
          ))}
        </GridLayout>
      )}
    </div>
  );
}
