"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, SETTINGS } from "@/lib/nav";

function NavLink({
  href,
  label,
  Icon,
  active,
}: {
  href: string;
  label: string;
  Icon: (typeof NAV)[number]["icon"];
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
        active
          ? "bg-ink text-paper"
          : "text-ink-soft hover:bg-paper-2 hover:text-ink"
      }`}
    >
      <Icon size={18} strokeWidth={1.9} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="flex w-60 flex-none flex-col border-r border-hairline bg-paper">
      {/* brand lockup — echoes the landing */}
      <div className="flex items-center gap-2.5 border-b border-hairline px-5 py-4">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-ink text-xs font-bold text-paper">
          E
        </span>
        <div className="leading-tight">
          <div className="font-display text-sm font-bold tracking-tight">Elda</div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-ink-soft">
            Elderly care robotics
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {NAV.map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            Icon={item.icon}
            active={isActive(item.href)}
          />
        ))}
      </nav>

      <div className="border-t border-hairline p-3">
        <NavLink
          href={SETTINGS.href}
          label={SETTINGS.label}
          Icon={SETTINGS.icon}
          active={isActive(SETTINGS.href)}
        />
        <div className="mt-3 flex items-center justify-between px-3 text-[10px] uppercase tracking-[0.15em] text-ink-soft/70">
          <span>Munich 2026</span>
          <span className="font-cjk">香港</span>
        </div>
      </div>
    </aside>
  );
}
