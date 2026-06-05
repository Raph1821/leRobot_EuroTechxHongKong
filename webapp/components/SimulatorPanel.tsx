"use client";

import { useState } from "react";
import { JOINTS, radToDeg, type JointValues } from "@/lib/joints";
import {
  Activity,
  Cpu,
  Thermometer,
  Zap,
  RotateCcw,
  Play,
  Pause,
  AlertTriangle,
} from "lucide-react";

/**
 * SimulatorPanel — Gazebo / physics simulation diagnostics.
 *
 * When the web interface is connected to the ROS2 WebSocket bridge,
 * moving the 3D model sliders will move the real robot in real time.
 * This panel shows the physical simulation parameters (Gazebo Harmonic)
 * so that technical problems can be diagnosed at a glance.
 *
 * Sections:
 *  1. Simulation status (running/paused/step, real-time factor)
 *  2. Joint diagnostics (torque, velocity, temperature per joint)
 *  3. Physics engine parameters (gravity, step size, solver iterations)
 *  4. Connection health (WebSocket bridge latency, packet loss)
 */

type PhysicsConfig = {
  gravity: [number, number, number];
  stepSize: number;
  realTimeFactor: number;
  solverIterations: number;
  frictionModel: string;
};

const DEFAULT_PHYSICS: PhysicsConfig = {
  gravity: [0, 0, -9.81],
  stepSize: 0.001,
  realTimeFactor: 1.0,
  solverIterations: 50,
  frictionModel: "pyramid_model",
};

export default function SimulatorPanel({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  const [simRunning, setSimRunning] = useState(true);
  const [physics, setPhysics] = useState<PhysicsConfig>(DEFAULT_PHYSICS);

  // Mock diagnostic data (in production, this comes from the ROS2 bridge)
  const jointDiagnostics = JOINTS.map((j) => ({
    name: j.label,
    position: jointValues[j.name] ?? 0,
    velocity: Math.random() * 0.1 - 0.05,
    torque: Math.random() * 2.0,
    temperature: 28 + Math.random() * 12,
    status: Math.random() > 0.9 ? ("warn" as const) : ("ok" as const),
  }));

  return (
    <div className="flex flex-col gap-5 p-5">
      {/* ─── Simulation Status ──────────────────── */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-display text-xs font-semibold uppercase tracking-[0.18em] text-ink">
            Gazebo · SO-101
          </h3>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              simRunning
                ? "bg-emerald-500/15 text-emerald-700"
                : "bg-gold/20 text-gold"
            }`}
          >
            {simRunning ? "Running" : "Paused"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setSimRunning(!simRunning)}
            className="grid h-8 w-8 place-items-center rounded-lg border border-hairline text-ink-soft transition-colors hover:bg-ink hover:text-paper"
          >
            {simRunning ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button className="grid h-8 w-8 place-items-center rounded-lg border border-hairline text-ink-soft transition-colors hover:bg-ink hover:text-paper">
            <RotateCcw size={14} />
          </button>
          <div className="ml-auto text-right">
            <div className="text-[11px] text-ink-soft">Real-time factor</div>
            <div className="font-mono text-sm font-semibold tabular-nums">
              {physics.realTimeFactor.toFixed(2)}x
            </div>
          </div>
        </div>
      </section>

      <div className="rule" />

      {/* ─── Joint Diagnostics ──────────────────── */}
      <section>
        <h3 className="font-display mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-ink">
          Joint Diagnostics
        </h3>
        <div className="space-y-2">
          {jointDiagnostics.map((jd) => (
            <div
              key={jd.name}
              className="rounded-lg border border-hairline px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">{jd.name}</span>
                {jd.status === "warn" && (
                  <AlertTriangle size={12} className="text-gold" />
                )}
              </div>
              <div className="mt-1.5 grid grid-cols-4 gap-2 text-[10px]">
                <div>
                  <span className="text-ink-soft">Pos</span>
                  <div className="font-mono font-medium tabular-nums">
                    {radToDeg(jd.position).toFixed(1)}°
                  </div>
                </div>
                <div>
                  <span className="text-ink-soft">Vel</span>
                  <div className="font-mono font-medium tabular-nums">
                    {jd.velocity.toFixed(3)}
                  </div>
                </div>
                <div>
                  <span className="text-ink-soft">Torque</span>
                  <div className="font-mono font-medium tabular-nums">
                    {jd.torque.toFixed(2)} Nm
                  </div>
                </div>
                <div>
                  <span className="text-ink-soft">Temp</span>
                  <div
                    className={`font-mono font-medium tabular-nums ${
                      jd.temperature > 35 ? "text-coral" : ""
                    }`}
                  >
                    {jd.temperature.toFixed(0)}°C
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="rule" />

      {/* ─── Physics Parameters ──────────────────── */}
      <section>
        <h3 className="font-display mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-ink">
          Physics Engine
        </h3>
        <div className="space-y-2 text-xs">
          <Row
            icon={<Activity size={12} />}
            label="Gravity"
            value={`[${physics.gravity.join(", ")}] m/s²`}
          />
          <Row
            icon={<Cpu size={12} />}
            label="Step size"
            value={`${physics.stepSize * 1000} ms`}
          />
          <Row
            icon={<Zap size={12} />}
            label="Solver iterations"
            value={`${physics.solverIterations}`}
          />
          <Row
            icon={<Thermometer size={12} />}
            label="Friction model"
            value={physics.frictionModel}
          />
        </div>
      </section>

      <div className="rule" />

      {/* ─── Connection Health ──────────────────── */}
      <section>
        <h3 className="font-display mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-ink">
          Bridge Connection
        </h3>
        <div className="space-y-2 text-xs">
          <Row label="WebSocket" value="ws://localhost:9090" />
          <Row label="Latency" value="3 ms" />
          <Row label="Joint state Hz" value="30 Hz" />
          <Row label="Packet loss" value="0.0%" />
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-soft">
          Moving sliders in Manual Control sends joint commands through the
          WebSocket bridge to both the Gazebo simulation and the real SO-101
          hardware simultaneously.
        </p>
      </section>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-md bg-paper-2/60 px-3 py-2">
      <span className="flex items-center gap-2 text-ink-soft">
        {icon}
        {label}
      </span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}
