import { Maximize2, Circle, Crosshair, Camera as Cam } from "lucide-react";

export default function CameraPage() {
  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div className="relative flex-1 overflow-hidden rounded-2xl border border-hairline bg-ink">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.08),transparent_65%)]" />
        {/* crosshair */}
        <Crosshair
          size={48}
          strokeWidth={1}
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-paper/25"
        />
        {/* hud */}
        <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/40 px-2 py-1 text-[11px] font-medium text-paper">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-coral" /> LIVE · CAM 1
        </span>
        <span className="absolute right-3 top-3 font-mono text-[11px] text-paper/60">
          1920×1080 · 30fps
        </span>
        <span className="absolute bottom-3 left-3 font-mono text-[11px] text-paper/60">
          2026-06-03 14:02:31
        </span>
        {/* controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          {[Circle, Cam, Maximize2].map((Icon, i) => (
            <button
              key={i}
              className="grid h-9 w-9 place-items-center rounded-lg bg-black/40 text-paper transition-colors hover:bg-black/60"
            >
              <Icon size={16} />
            </button>
          ))}
        </div>
      </div>

      {/* thumbnails */}
      <div className="grid grid-cols-4 gap-3">
        {["Front", "Gripper", "Top", "Room"].map((label, i) => (
          <div
            key={label}
            className={`relative aspect-video overflow-hidden rounded-xl border bg-ink ${
              i === 0 ? "border-coral" : "border-hairline"
            }`}
          >
            <span className="absolute bottom-1.5 left-2 text-[10px] font-medium text-paper/70">
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
