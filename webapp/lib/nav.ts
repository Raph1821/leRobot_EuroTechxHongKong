import {
  LayoutDashboard,
  Bot,
  Video,
  CalendarDays,
  Pill,
  Activity,
  MessageCircle,
  MessageSquare,
  Users,
  Siren,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "./role";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** which role spaces show this item */
  roles: Role[];
};

export const NAV: NavItem[] = [
  // ── patient space (the original dashboard) ──
  { href: "/", label: "Overview", icon: LayoutDashboard, roles: ["patient"] },
  { href: "/control", label: "Simulation & Control", icon: Bot, roles: ["patient"] },
  { href: "/camera", label: "Camera", icon: Video, roles: ["patient"] },
  { href: "/interaction", label: "Interaction", icon: MessageCircle, roles: ["patient"] },
  { href: "/schedule", label: "Schedule", icon: CalendarDays, roles: ["patient"] },
  { href: "/medications", label: "Medications", icon: Pill, roles: ["patient"] },
  { href: "/reports", label: "Reports & Alerts", icon: Activity, roles: ["patient"] },
  { href: "/emergency", label: "Emergency", icon: Siren, roles: ["patient"] },
  // ── care team spaces ──
  { href: "/patients", label: "Patients", icon: Users, roles: ["nurse", "doctor"] },
  // ── shared ──
  { href: "/messages", label: "Messages", icon: MessageSquare, roles: ["patient", "nurse", "doctor"] },
];

export const SETTINGS: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
  roles: ["patient", "nurse", "doctor"],
};

export function titleFor(pathname: string): string {
  const match = [...NAV, SETTINGS]
    .filter((i) =>
      i.href === "/" ? pathname === "/" : pathname.startsWith(i.href),
    )
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.label ?? "Overview";
}
