"use client";

import { JOINTS, radToDeg, type JointValues } from "@/lib/joints";

export default function ControlPanel({
  values,
  onChange,
  onHome,
}: {
  values: JointValues;
  onChange: (name: string, value: number) => void;
  onHome: () => void;
}) {
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-7">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
            Manual Control
          </h2>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-ink-soft">
            SO-101 · 6 DOF
          </p>
        </div>
        <button
          onClick={onHome}
          className="font-display rounded-full border border-ink/20 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-ink transition-colors hover:bg-ink hover:text-paper"
        >
          Home
        </button>
      </div>

      <div className="rule" />

      <div className="flex flex-col gap-5">
        {JOINTS.map((j) => {
          const v = values[j.name] ?? 0;
          return (
            <div key={j.name}>
              <div className="mb-1.5 flex items-baseline justify-between">
                <label
                  htmlFor={j.name}
                  className="text-sm font-medium text-ink"
                >
                  {j.label}
                </label>
                <span className="font-mono text-xs tabular-nums font-semibold text-coral">
                  {radToDeg(v).toFixed(1)}°
                </span>
              </div>
              <input
                id={j.name}
                type="range"
                min={j.lower}
                max={j.upper}
                step={0.001}
                value={v}
                onChange={(e) => onChange(j.name, parseFloat(e.target.value))}
                className="slider w-full"
              />
              <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-soft/60">
                <span>{radToDeg(j.lower).toFixed(0)}°</span>
                <span>{radToDeg(j.upper).toFixed(0)}°</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
