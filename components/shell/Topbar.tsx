"use client";

import { usePathname } from "next/navigation";
import { titleFor } from "@/lib/nav";

export default function Topbar() {
  const pathname = usePathname();
  return (
    <header className="flex flex-none items-center justify-between border-b border-hairline bg-paper px-6 py-3.5">
      <h1 className="font-display text-lg font-bold tracking-tight">
        {titleFor(pathname)}
      </h1>
      <div className="flex items-center gap-4 text-xs uppercase tracking-[0.18em] text-ink-soft">
        <span className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          SO-101 · Online
        </span>
        <span className="hidden sm:block">AI &amp; Robotics</span>
      </div>
    </header>
  );
}
