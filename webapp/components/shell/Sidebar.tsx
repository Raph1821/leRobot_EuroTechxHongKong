"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronsUpDown, LogOut } from "lucide-react";
import { NAV, SETTINGS } from "@/lib/nav";
import { ACCOUNTS, ROLE_LABELS, useRole, type Role } from "@/lib/role";

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
  const router = useRouter();
  const { role, account, signIn, signOut } = useRole();
  const [menuOpen, setMenuOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const switchAccount = (r: Role) => {
    setMenuOpen(false);
    if (r === role) return;
    signIn(r);
    router.push(r === "patient" ? "/" : "/patients");
  };

  const items = NAV.filter((i) => i.roles.includes(role));

  return (
    <aside className="flex w-60 flex-none flex-col border-r border-hairline bg-paper">
      {/* brand lockup — echoes the landing */}
      <div className="flex items-center gap-2.5 border-b border-hairline px-5 py-4">
        <div className="leading-tight">
          <div className="font-logo text-[70px] leading-none">ELDA</div>
          <div className="text-[10px] tracking-[0.08em] text-ink-soft">
            Elderly Care Robotics
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {items.map((item) => (
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

        {/* account switcher — simulated session (beta) */}
        <div className="relative mt-2">
          {menuOpen && (
            <div className="absolute bottom-full left-0 right-0 z-30 mb-2 overflow-hidden rounded-xl border border-hairline bg-paper shadow-[0_16px_50px_-20px_rgba(14,17,22,0.45)]">
              {ACCOUNTS.filter((a) => a.role !== role).map((a) => (
                <button
                  key={a.role}
                  onClick={() => switchAccount(a.role)}
                  className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-paper-2"
                >
                  <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-paper-2 text-[11px] font-bold">
                    {a.initials}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{a.name}</span>
                    <span className="text-[10px] uppercase tracking-wider text-ink-soft">
                      {ROLE_LABELS[a.role]}
                    </span>
                  </span>
                </button>
              ))}
              <button
                onClick={() => {
                  setMenuOpen(false);
                  signOut();
                }}
                className="flex w-full items-center gap-2.5 border-t border-hairline px-3 py-2.5 text-left text-sm text-coral hover:bg-coral/5"
              >
                <LogOut size={15} /> Log out
              </button>
            </div>
          )}

          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="flex w-full items-center gap-2.5 rounded-xl border border-hairline px-3 py-2.5 text-left transition-colors hover:bg-paper-2"
          >
            <span className="grid h-8 w-8 flex-none place-items-center rounded-full bg-ink text-[11px] font-bold text-paper">
              {account.initials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{account.name}</span>
              <span className="text-[10px] uppercase tracking-wider text-ink-soft">
                {ROLE_LABELS[role]}
              </span>
            </span>
            <ChevronsUpDown size={14} className="flex-none text-ink-soft" />
          </button>
        </div>

      </div>
    </aside>
  );
}
