"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import ControlPanel from "./ControlPanel";
import SimulatorPanel from "./SimulatorPanel";
import { useJoints } from "@/lib/jointStore";

// three.js must not run on the server
const RobotViewer = dynamic(() => import("./RobotViewer"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center text-sm uppercase tracking-[0.2em] text-ink-soft">
      Loading 3D scene…
    </div>
  ),
});

type Tab = "control" | "simulator";

export default function ManualControl() {
  const { values, setJoint, home } = useJoints();
  const [activeTab, setActiveTab] = useState<Tab>("control");

  return (
    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[1fr_400px]">
      {/* 3D viewer — commands sent here also move the real robot via WebSocket bridge */}
      <div className="relative min-h-[55vh] lg:min-h-0">
        <div className="absolute inset-0">
          <RobotViewer jointValues={values} />
        </div>
        {/* Connection status badge */}
        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-black/50 px-2.5 py-1 text-[11px] font-medium text-paper">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          SIM + HARDWARE LINKED
        </div>
      </div>

      {/* Right panel — tabs for Manual Control vs Simulator Diagnostics */}
      <aside className="flex min-h-0 flex-col border-t border-hairline bg-paper-2/40 lg:border-l lg:border-t-0">
        {/* Tab switcher */}
        <div className="flex border-b border-hairline">
          <button
            onClick={() => setActiveTab("control")}
            className={`flex-1 py-3 text-center text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === "control"
                ? "border-b-2 border-ink text-ink"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Manual Control
          </button>
          <button
            onClick={() => setActiveTab("simulator")}
            className={`flex-1 py-3 text-center text-xs font-semibold uppercase tracking-wider transition-colors ${
              activeTab === "simulator"
                ? "border-b-2 border-ink text-ink"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Simulator
          </button>
        </div>

        {/* Tab content */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {activeTab === "control" ? (
            <ControlPanel values={values} onChange={setJoint} onHome={home} />
          ) : (
            <SimulatorPanel jointValues={values} />
          )}
        </div>
      </aside>
    </div>
  );
}
