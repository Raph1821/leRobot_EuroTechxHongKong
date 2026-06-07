"use client";

import { useState } from "react";
import { Play, Square, Radio, Circle } from "lucide-react";
import { useJoints } from "@/lib/jointStore";
import { JOINTS, radToDeg, type JointValues } from "@/lib/joints";

export default function TeleopPanel() {
  const { values, status, startTeleop, stopTeleop, startRecording, stopRecording } = useJoints();
  const [teleopActive, setTeleopActive] = useState(false);
  const [recording, setRecording] = useState(false);

  const handleStartTeleop = () => {
    startTeleop();
    setTeleopActive(true);
  };

  const handleStopTeleop = () => {
    stopTeleop();
    if (recording) {
      stopRecording();
      setRecording(false);
    }
    setTeleopActive(false);
  };

  const handleToggleRecording = () => {
    if (recording) {
      stopRecording();
      setRecording(false);
    } else {
      startRecording();
      setRecording(true);
    }
  };

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-7">
      <div>
        <h2 className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
          Teleoperation
        </h2>
        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-ink-soft">
          Leader-Follower Control
        </p>
      </div>

      <div className="rule" />

      {/* Connection Status */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
            Status
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
                ? "Bridge Online"
                : status === "connecting"
                  ? "Connecting..."
                  : "Offline"}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
            Teleop Mode
          </span>
          <span
            className={`text-xs font-medium uppercase tracking-wider ${
              teleopActive ? "text-emerald-500" : "text-ink-soft"
            }`}
          >
            {teleopActive ? "Active" : "Inactive"}
          </span>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex flex-col gap-3">
        {!teleopActive ? (
          <button
            onClick={handleStartTeleop}
            disabled={status !== "online"}
            className="flex items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-emerald-600 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            Start Teleop
          </button>
        ) : (
          <>
            <button
              onClick={handleStopTeleop}
              className="flex items-center justify-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-red-600 transition-colors hover:bg-red-500/20"
            >
              <Square className="h-4 w-4" />
              Stop Teleop
            </button>
            <button
              onClick={handleToggleRecording}
              className={`flex items-center justify-center gap-2 rounded-lg border py-3 font-display text-sm font-semibold uppercase tracking-wider transition-colors ${
                recording
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-600 hover:bg-amber-500/20"
                  : "border-ink/20 bg-paper-2/40 text-ink hover:bg-ink/5"
              }`}
            >
              {recording ? (
                <>
                  <Circle className="h-4 w-4 animate-pulse fill-current" />
                  Stop Recording
                </>
              ) : (
                <>
                  <Radio className="h-4 w-4" />
                  Start Recording
                </>
              )}
            </button>
          </>
        )}
      </div>

      <div className="rule" />

      {/* Leader Arm Position Display */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-soft">
          Leader Arm Position
        </h3>
        <div className="flex flex-col gap-3">
          {JOINTS.map((j) => {
            const v = values[j.name] ?? 0;
            return (
              <div
                key={j.name}
                className="flex items-center justify-between rounded border border-hairline bg-paper-2/40 px-3 py-2"
              >
                <span className="text-xs font-medium text-ink">{j.label}</span>
                <span className="font-mono text-xs font-semibold tabular-nums text-coral">
                  {radToDeg(v).toFixed(1)}°
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Info Section */}
      <div className="mt-auto rounded-lg border border-hairline bg-paper-2/40 p-4">
        <p className="text-xs leading-relaxed text-ink-soft">
          Teleoperation allows you to control the follower robot arm by
          manipulating the leader arm. The follower will mirror the leader's
          movements in real-time.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-ink-soft">
          Use <span className="font-semibold text-ink">Recording</span> to
          capture episodes for training.
        </p>
      </div>
    </div>
  );
}
