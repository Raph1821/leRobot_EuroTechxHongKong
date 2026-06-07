"use client";

import { useState } from "react";
import KeyboardControl from "./KeyboardControl";
import CartesianControl from "./CartesianControl";
import EpisodeRecorder from "./EpisodeRecorder";
import { useJoints } from "@/lib/jointStore";

type ControlMode = "keyboard" | "cartesian" | "recorder";

export default function TeleopPanel() {
  const { status } = useJoints();
  const [activeMode, setActiveMode] = useState<ControlMode>("keyboard");

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-7">
      <div>
        <h2 className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
          Robot Control
        </h2>
        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-ink-soft">
          Advanced Control Modes
        </p>
      </div>

      <div className="rule" />

      {/* Connection Status */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
            Bridge Status
          </span>
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                status === "online"
                  ? "bg-emerald-400"
                  : status === "connecting"
                    ? "animate-pulse bg-amber-400"
                    : "bg-red-400"
              }`}
            />
            <span className="text-xs font-medium uppercase tracking-wider text-ink">
              {status === "online"
                ? "Online"
                : status === "connecting"
                  ? "Connecting..."
                  : "Offline"}
            </span>
          </div>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="flex gap-2 rounded-lg border border-hairline bg-paper-2/40 p-1">
        <button
          onClick={() => setActiveMode("keyboard")}
          className={`flex-1 rounded px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
            activeMode === "keyboard"
              ? "bg-ink text-paper"
              : "text-ink-soft hover:text-ink"
          }`}
        >
          Keyboard
        </button>
        <button
          onClick={() => setActiveMode("cartesian")}
          className={`flex-1 rounded px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
            activeMode === "cartesian"
              ? "bg-ink text-paper"
              : "text-ink-soft hover:text-ink"
          }`}
        >
          Cartesian
        </button>
        <button
          onClick={() => setActiveMode("recorder")}
          className={`flex-1 rounded px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
            activeMode === "recorder"
              ? "bg-ink text-paper"
              : "text-ink-soft hover:text-ink"
          }`}
        >
          Recorder
        </button>
      </div>

      <div className="rule" />

      {/* Active Mode Content */}
      {activeMode === "keyboard" && <KeyboardControl />}
      {activeMode === "cartesian" && <CartesianControl />}
      {activeMode === "recorder" && <EpisodeRecorder />}
    </div>
  );
}
