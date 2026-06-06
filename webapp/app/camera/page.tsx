"use client";

import { useRef } from "react";
import { Maximize2, Camera as Cam, Crosshair } from "lucide-react";
import { useJoints } from "@/lib/jointStore";

export default function CameraPage() {
  const { cameraFrame, status } = useJoints();
  const frameRef = useRef<HTMLDivElement>(null);

  const live = !!cameraFrame;
  const src = cameraFrame
    ? `data:image/${cameraFrame.encoding};base64,${cameraFrame.data}`
    : "";

  const snapshot = () => {
    if (!src) return;
    const a = document.createElement("a");
    a.href = src;
    a.download = `elda-snapshot.${cameraFrame!.encoding}`;
    a.click();
  };

  const fullscreen = () => {
    const el = frameRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen?.();
  };

  return (
    <div className="h-full p-6">
      <div
        ref={frameRef}
        className="relative h-full overflow-hidden rounded-2xl border border-hairline bg-ink"
      >
        {live ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="Robot camera" className="h-full w-full object-cover" />
        ) : (
          <>
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.08),transparent_65%)]" />
            <Crosshair
              size={48}
              strokeWidth={1}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-paper/25"
            />
            <span className="absolute left-1/2 top-[58%] -translate-x-1/2 text-xs uppercase tracking-[0.2em] text-paper/40">
              {status === "online" ? "Waiting for stream…" : "No signal · bridge offline"}
            </span>
          </>
        )}

        {/* hud */}
        <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/40 px-2 py-1 text-[11px] font-medium text-paper">
          <span
            className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-coral" : "bg-paper/40"}`}
          />
          {live ? "LIVE · CAM 1" : "OFFLINE"}
        </span>
        {live && (
          <span className="absolute right-3 top-3 font-mono text-[11px] text-paper/60">
            {cameraFrame.width}×{cameraFrame.height}
          </span>
        )}

        {/* controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          <button
            onClick={snapshot}
            disabled={!live}
            aria-label="Snapshot"
            className="grid h-9 w-9 place-items-center rounded-lg bg-black/40 text-paper transition-colors hover:bg-black/60 disabled:opacity-40"
          >
            <Cam size={16} />
          </button>
          <button
            onClick={fullscreen}
            aria-label="Fullscreen"
            className="grid h-9 w-9 place-items-center rounded-lg bg-black/40 text-paper transition-colors hover:bg-black/60"
          >
            <Maximize2 size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
