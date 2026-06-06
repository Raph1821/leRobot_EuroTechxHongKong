"use client";

import { useRef, useState } from "react";
import { Maximize2, Camera as Cam, Crosshair } from "lucide-react";

const STREAM_URL = "http://localhost:8000/camera/stream";
const SNAPSHOT_URL = "http://localhost:8000/camera/snapshot";

export default function CameraPage() {
  const frameRef = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(false);

  const snapshot = async () => {
    if (!live) return;
    try {
      const res = await fetch(SNAPSHOT_URL);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "careai-snapshot.jpg";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // stream offline
    }
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
        {/* Always keep the img in the DOM so the MJPEG connection stays alive */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={STREAM_URL}
          alt="Robot camera"
          className="h-full w-full object-cover"
          onLoad={() => setLive(true)}
          onError={() => setLive(false)}
        />

        {/* Offline overlay — covers the img when stream is not yet live */}
        {!live && (
          <div className="absolute inset-0 bg-ink">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.08),transparent_65%)]" />
            <Crosshair
              size={48}
              strokeWidth={1}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-paper/25"
            />
            <span className="absolute left-1/2 top-[58%] -translate-x-1/2 text-xs uppercase tracking-[0.2em] text-paper/40">
              No signal · backend offline
            </span>
          </div>
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
            1920×1080
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
