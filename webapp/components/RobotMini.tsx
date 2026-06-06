"use client";

import { useEffect } from "react";
import { useSO101 } from "./RobotArm";
import type { JointValues } from "@/lib/joints";

// Independent SO-101 for the Overview widget (its own loaded instance).
export default function RobotMini({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  const robot = useSO101();

  useEffect(() => {
    if (!robot || typeof robot.setJointValue !== "function") return;
    for (const [name, value] of Object.entries(jointValues)) {
      robot.setJointValue(name, value);
    }
  }, [robot, jointValues]);

  if (!robot) return null;
  return <primitive object={robot} rotation={[-Math.PI / 2, 0, 0]} />;
}
