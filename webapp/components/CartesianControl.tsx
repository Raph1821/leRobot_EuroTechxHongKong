"use client";

import { useState } from "react";
import { Target, Send } from "lucide-react";
import { useJoints, type Vector3, type Quaternion } from "@/lib/jointStore";

export default function CartesianControl() {
  const { sendCartesianGoal, trajectoryStatus, status } = useJoints();
  
  const [position, setPosition] = useState<Vector3>({ x: 0.2, y: 0.0, z: 0.2 });
  const [duration, setDuration] = useState(2.0);
  const [useOrientation, setUseOrientation] = useState(false);
  const [orientation, setOrientation] = useState<Quaternion>({ x: 0, y: 0, z: 0, w: 1 });

  const handleSendGoal = () => {
    sendCartesianGoal(
      position,
      useOrientation ? orientation : undefined,
      duration
    );
  };

  const isExecuting = trajectoryStatus === "executing";

  // Workspace bounds (from backend)
  const bounds = {
    x: { min: -0.3, max: 0.3 },
    y: { min: -0.3, max: 0.3 },
    z: { min: 0.0, max: 0.5 },
  };

  const isInBounds = (axis: keyof Vector3, value: number) => {
    return value >= bounds[axis].min && value <= bounds[axis].max;
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-ink-soft" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
            Cartesian Control
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
              trajectoryStatus === "executing"
                ? "bg-amber-500/10 text-amber-600"
                : trajectoryStatus === "succeeded"
                  ? "bg-emerald-500/10 text-emerald-600"
                  : trajectoryStatus === "aborted"
                    ? "bg-red-500/10 text-red-600"
                    : "bg-paper-2/40 text-ink-soft"
            }`}
          >
            {trajectoryStatus}
          </span>
        </div>
      </div>

      {/* Position Controls */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-soft">
          Target Position (meters)
        </h4>
        
        <div className="flex flex-col gap-3">
          {(["x", "y", "z"] as const).map((axis) => {
            const value = position[axis];
            const inBounds = isInBounds(axis, value);
            
            return (
              <div key={axis}>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <label className="text-sm font-medium uppercase text-ink">
                    {axis}
                  </label>
                  <span
                    className={`font-mono text-xs tabular-nums font-semibold ${
                      inBounds ? "text-coral" : "text-red-500"
                    }`}
                  >
                    {value.toFixed(3)} m
                  </span>
                </div>
                <input
                  type="range"
                  min={bounds[axis].min}
                  max={bounds[axis].max}
                  step={0.001}
                  value={value}
                  onChange={(e) =>
                    setPosition((prev) => ({
                      ...prev,
                      [axis]: parseFloat(e.target.value),
                    }))
                  }
                  className="slider w-full"
                  disabled={isExecuting}
                />
                <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-soft/60">
                  <span>{bounds[axis].min.toFixed(1)}</span>
                  <span>{bounds[axis].max.toFixed(1)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Orientation Controls (Optional) */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
            Orientation (Quaternion)
          </h4>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useOrientation}
              onChange={(e) => setUseOrientation(e.target.checked)}
              className="rounded"
              disabled={isExecuting}
            />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-soft">
              Custom
            </span>
          </label>
        </div>

        {useOrientation && (
          <div className="grid grid-cols-2 gap-3">
            {(["x", "y", "z", "w"] as const).map((axis) => {
              const value = orientation[axis];
              return (
                <div key={axis}>
                  <div className="mb-1 flex items-baseline justify-between">
                    <label className="text-xs font-medium uppercase text-ink">
                      {axis}
                    </label>
                    <span className="font-mono text-xs tabular-nums font-semibold text-coral">
                      {value.toFixed(3)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={-1}
                    max={1}
                    step={0.01}
                    value={value}
                    onChange={(e) =>
                      setOrientation((prev) => ({
                        ...prev,
                        [axis]: parseFloat(e.target.value),
                      }))
                    }
                    className="slider w-full"
                    disabled={isExecuting}
                  />
                </div>
              );
            })}
          </div>
        )}

        {!useOrientation && (
          <p className="text-xs text-ink-soft">
            Using default orientation (identity quaternion)
          </p>
        )}
      </div>

      {/* Duration Control */}
      <div>
        <div className="mb-1.5 flex items-baseline justify-between">
          <label className="text-xs font-medium text-ink-soft">
            Movement Duration
          </label>
          <span className="font-mono text-xs font-semibold tabular-nums text-coral">
            {duration.toFixed(1)} sec
          </span>
        </div>
        <input
          type="range"
          min={0.5}
          max={10}
          step={0.1}
          value={duration}
          onChange={(e) => setDuration(parseFloat(e.target.value))}
          className="slider w-full"
          disabled={isExecuting}
        />
        <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-soft/60">
          <span>0.5s</span>
          <span>10.0s</span>
        </div>
      </div>

      {/* Send Button */}
      <button
        onClick={handleSendGoal}
        disabled={status !== "online" || isExecuting}
        className="flex items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-emerald-600 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Send className="h-4 w-4" />
        Send Goal
      </button>

      {/* Info */}
      <div className="rounded border border-hairline bg-paper-2/40 p-3 text-xs leading-relaxed text-ink-soft">
        <strong>Cartesian Control:</strong> Move the end-effector to a target position in 3D space. The backend uses inverse kinematics to calculate joint positions.
      </div>
    </div>
  );
}
