import {
  LayoutDashboard,
  Bot,
  Video,
  CalendarDays,
  Pill,
  Activity,
  MessageCircle,
  Siren,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const NAV: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/control", label: "Simulation & Control", icon: Bot },
  { href: "/camera", label: "Camera", icon: Video },
  { href: "/interaction", label: "Interaction", icon: MessageCircle },
  { href: "/assistant", label: "Assistant", icon: MessageCircle },
  { href: "/schedule", label: "Schedule", icon: CalendarDays },
  { href: "/medications", label: "Medications", icon: Pill },
  { href: "/reports", label: "Reports & Alerts", icon: Activity },
  { href: "/emergency", label: "Emergency", icon: Siren },
];

export const SETTINGS: NavItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

export function titleFor(pathname: string): string {
  const match = [...NAV, SETTINGS]
    .filter((i) =>
      i.href === "/" ? pathname === "/" : pathname.startsWith(i.href),
    )
    .sort((a, b) => b.href.length - a.href.length)[0];
  return match?.label ?? "Overview";
}
