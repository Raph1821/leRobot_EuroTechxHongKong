"use client";

import { useEffect, useRef, useState } from "react";
import { Keyboard, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, RotateCw, RotateCcw } from "lucide-react";
import { useJoints } from "@/lib/jointStore";

const VELOCITY_INCREMENT = 0.1; // m/s or rad/s
const MAX_VELOCITY = 0.2;

export default function KeyboardControl() {
  const { teleopEnabled, setTeleopMode, sendTeleopVelocity, status } = useJoints();
  const [velocityScale, setVelocityScale] = useState(0.05);
  const [activeKeys, setActiveKeys] = useState<Set<string>>(new Set());
  
  const velocityRef = useRef({
    linear: [0, 0, 0] as [number, number, number],
    angular: [0, 0, 0] as [number, number, number],
  });

  // Send velocity commands at 20Hz when teleop is active
  useEffect(() => {
    if (!teleopEnabled) return;

    const interval = setInterval(() => {
      sendTeleopVelocity(velocityRef.current.linear, velocityRef.current.angular);
    }, 50); // 20Hz

    return () => clearInterval(interval);
  }, [teleopEnabled, sendTeleopVelocity]);

  // Handle keyboard input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!teleopEnabled) return;
      
      setActiveKeys((prev) => new Set(prev).add(e.key.toLowerCase()));
      
      const vel = velocityRef.current;
      const scale = velocityScale;

      switch (e.key.toLowerCase()) {
        // Linear movement
        case "w":
        case "arrowup":
          vel.linear[0] = scale; // +X (forward)
          break;
        case "s":
        case "arrowdown":
          vel.linear[0] = -scale; // -X (backward)
          break;
        case "a":
        case "arrowleft":
          vel.linear[1] = scale; // +Y (left)
          break;
        case "d":
        case "arrowright":
          vel.linear[1] = -scale; // -Y (right)
          break;
        case "q":
          vel.linear[2] = scale; // +Z (up)
          break;
        case "e":
          vel.linear[2] = -scale; // -Z (down)
          break;
          
        // Angular movement
        case "j":
          vel.angular[2] = scale; // +Yaw (rotate left)
          break;
        case "l":
          vel.angular[2] = -scale; // -Yaw (rotate right)
          break;
        case "i":
          vel.angular[1] = scale; // +Pitch (tilt up)
          break;
        case "k":
          vel.angular[1] = -scale; // -Pitch (tilt down)
          break;
        case "u":
          vel.angular[0] = scale; // +Roll (roll left)
          break;
        case "o":
          vel.angular[0] = -scale; // -Roll (roll right)
          break;
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (!teleopEnabled) return;
      
      setActiveKeys((prev) => {
        const next = new Set(prev);
        next.delete(e.key.toLowerCase());
        return next;
      });

      const vel = velocityRef.current;

      switch (e.key.toLowerCase()) {
        case "w":
        case "s":
        case "arrowup":
        case "arrowdown":
          vel.linear[0] = 0;
          break;
        case "a":
        case "d":
        case "arrowleft":
        case "arrowright":
          vel.linear[1] = 0;
          break;
        case "q":
        case "e":
          vel.linear[2] = 0;
          break;
        case "j":
        case "l":
          vel.angular[2] = 0;
          break;
        case "i":
        case "k":
          vel.angular[1] = 0;
          break;
        case "u":
        case "o":
          vel.angular[0] = 0;
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [teleopEnabled, velocityScale]);

  const handleToggleTeleop = () => {
    if (teleopEnabled) {
      setTeleopMode(false);
      // Reset velocity
      velocityRef.current = {
        linear: [0, 0, 0],
        angular: [0, 0, 0],
      };
      setActiveKeys(new Set());
    } else {
      setTeleopMode(true, velocityScale);
    }
  };

  const handleVelocityChange = (value: number) => {
    setVelocityScale(value);
    if (teleopEnabled) {
      setTeleopMode(true, value);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Keyboard className="h-4 w-4 text-ink-soft" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
            Keyboard Control
          </h3>
        </div>
        <button
          onClick={handleToggleTeleop}
          disabled={status !== "online"}
          className={`rounded px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-colors ${
            teleopEnabled
              ? "border border-red-500/30 bg-red-500/10 text-red-600 hover:bg-red-500/20"
              : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
          } disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {teleopEnabled ? "Stop" : "Start"}
        </button>
      </div>

      {/* Velocity Scale Slider */}
      <div>
        <div className="mb-1.5 flex items-baseline justify-between">
          <label className="text-xs font-medium text-ink-soft">
            Velocity Scale
          </label>
          <span className="font-mono text-xs font-semibold tabular-nums text-coral">
            {velocityScale.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0.01}
          max={0.2}
          step={0.01}
          value={velocityScale}
          onChange={(e) => handleVelocityChange(parseFloat(e.target.value))}
          className="slider w-full"
        />
        <div className="mt-1 flex justify-between font-mono text-[10px] text-ink-soft/60">
          <span>0.01</span>
          <span>0.20</span>
        </div>
      </div>

      {/* Key Mapping Guide */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-soft">
          Controls
        </h4>
        
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <div>
            <div className="mb-1 font-semibold text-ink">Linear Movement</div>
            <div className="flex flex-col gap-1 text-ink-soft">
              <div className="flex items-center justify-between">
                <span>W / ↑</span>
                <span className="text-[10px]">Forward</span>
              </div>
              <div className="flex items-center justify-between">
                <span>S / ↓</span>
                <span className="text-[10px]">Backward</span>
              </div>
              <div className="flex items-center justify-between">
                <span>A / ←</span>
                <span className="text-[10px]">Left</span>
              </div>
              <div className="flex items-center justify-between">
                <span>D / →</span>
                <span className="text-[10px]">Right</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Q</span>
                <span className="text-[10px]">Up</span>
              </div>
              <div className="flex items-center justify-between">
                <span>E</span>
                <span className="text-[10px]">Down</span>
              </div>
            </div>
          </div>

          <div>
            <div className="mb-1 font-semibold text-ink">Angular Movement</div>
            <div className="flex flex-col gap-1 text-ink-soft">
              <div className="flex items-center justify-between">
                <span>J</span>
                <span className="text-[10px]">Yaw Left</span>
              </div>
              <div className="flex items-center justify-between">
                <span>L</span>
                <span className="text-[10px]">Yaw Right</span>
              </div>
              <div className="flex items-center justify-between">
                <span>I</span>
                <span className="text-[10px]">Pitch Up</span>
              </div>
              <div className="flex items-center justify-between">
                <span>K</span>
                <span className="text-[10px]">Pitch Down</span>
              </div>
              <div className="flex items-center justify-between">
                <span>U</span>
                <span className="text-[10px]">Roll Left</span>
              </div>
              <div className="flex items-center justify-between">
                <span>O</span>
                <span className="text-[10px]">Roll Right</span>
              </div>
            </div>
          </div>
        </div>

        {/* Active Keys Indicator */}
        {activeKeys.size > 0 && (
          <div className="mt-3 rounded border border-emerald-500/30 bg-emerald-500/10 p-2">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600">
              Active: {Array.from(activeKeys).join(", ").toUpperCase()}
            </div>
          </div>
        )}
      </div>

      {/* Safety Notice */}
      <div className="rounded border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-700">
        <strong>Safety:</strong> Release all keys to stop movement. The robot will stop immediately when teleop mode is disabled.
      </div>
    </div>
  );
}
