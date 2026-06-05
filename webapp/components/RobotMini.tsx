"use client";

import { useEffect, useMemo } from "react";
import { useLoader } from "@react-three/fiber";
import * as THREE from "three";
import URDFLoader, { type URDFRobot } from "urdf-loader";
import { URDF_URL, type JointValues } from "@/lib/joints";
import { configureURDFLoader } from "./RobotArm";

// A second, independent SO-101 for the Overview widget. useLoader caches one
// robot object (can't live in two scenes), so we clone it for this canvas.
export default function RobotMini({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  const base = useLoader(
    URDFLoader as unknown as new () => THREE.Loader,
    URDF_URL,
    (loader) => configureURDFLoader(loader as unknown as URDFLoader),
  ) as unknown as URDFRobot;

  const robot = useMemo(
    () => base.clone(true) as unknown as URDFRobot,
    [base],
  );

  useEffect(() => {
    if (!robot || typeof robot.setJointValue !== "function") return;
    for (const [name, value] of Object.entries(jointValues)) {
      robot.setJointValue(name, value);
    }
  }, [robot, jointValues]);

  return <primitive object={robot} rotation={[-Math.PI / 2, 0, 0]} />;
}
