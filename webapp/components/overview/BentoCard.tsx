import Link from "next/link";
import { ArrowUpRight, type LucideIcon } from "lucide-react";

export default function BentoCard({
  href,
  title,
  Icon,
  accent = "var(--ink)",
  className = "",
  children,
}: {
  href: string;
  title: string;
  Icon: LucideIcon;
  accent?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-hairline bg-paper p-5 transition-all hover:-translate-y-0.5 hover:border-ink/30 hover:shadow-[0_12px_40px_-20px_rgba(14,17,22,0.4)] ${className}`}
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="flex items-center gap-2.5">
          <span
            className="grid h-8 w-8 place-items-center rounded-lg text-paper"
            style={{ backgroundColor: accent }}
          >
            <Icon size={16} strokeWidth={2} />
          </span>
          <span className="font-display text-sm font-semibold tracking-tight">
            {title}
          </span>
        </span>
        <ArrowUpRight
          size={16}
          className="text-ink-soft transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
        />
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </Link>
  );
}
