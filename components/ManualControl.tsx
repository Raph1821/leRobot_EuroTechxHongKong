"use client";

import dynamic from "next/dynamic";
import ControlPanel from "./ControlPanel";
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

export default function ManualControl() {
  const { values, setJoint, home } = useJoints();

  return (
    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[1fr_360px]">
      {/* viewer — explicit min-h so the Canvas always has height to fill */}
      <div className="relative min-h-[55vh] lg:min-h-0">
        <div className="absolute inset-0">
          <RobotViewer jointValues={values} />
        </div>
      </div>
      <aside className="min-h-0 overflow-y-auto border-t border-hairline bg-paper-2/40 lg:border-l lg:border-t-0">
        <ControlPanel values={values} onChange={setJoint} onHome={home} />
      </aside>
    </div>
  );
}
