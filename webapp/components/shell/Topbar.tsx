"use client";

import { usePathname } from "next/navigation";
import { titleFor } from "@/lib/nav";
import { useJoints } from "@/lib/jointStore";

const STATUS = {
  online: { dot: "bg-emerald-500", ping: true, label: "SO-101 · Online" },
  connecting: { dot: "bg-gold", ping: true, label: "Connecting…" },
  offline: { dot: "bg-ink-soft/40", ping: false, label: "Offline · local" },
} as const;

export default function Topbar() {
  const pathname = usePathname();
  const { status } = useJoints();
  const s = STATUS[status];
  return (
    <header className="flex flex-none items-center justify-between border-b border-hairline bg-paper px-6 py-3.5">
      <h1 className="font-display text-lg font-bold tracking-tight">
        {titleFor(pathname)}
      </h1>
      <div className="flex items-center gap-4 text-xs uppercase tracking-[0.18em] text-ink-soft">
        <span className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            {s.ping && (
              <span
                className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${s.dot}`}
              />
            )}
            <span className={`relative inline-flex h-2 w-2 rounded-full ${s.dot}`} />
          </span>
          {s.label}
        </span>
      </div>
    </header>
  );
}
