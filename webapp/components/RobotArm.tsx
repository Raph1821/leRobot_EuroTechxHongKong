"use client";

import { useEffect, useState } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import URDFLoader, { type URDFRobot } from "urdf-loader";
import { URDF_URL, type JointValues } from "@/lib/joints";

// ── Part palette (landing colours). Tweak any role here. ──
export const PART_COLORS = {
  primary: "#ff3b53", // structural arm links — coral
  secondary: "#0e1116", // STS3215 servos — ink
  accent: "#d9a441", // wrist + gripper + jaw — gold
  base: "#0e4fe0", // base & motor mounts — harbour blue
} as const;

// classify a mesh by its source STL filename → colour role
export function colorFor(filename: string): string {
  const f = filename.toLowerCase();
  if (f.includes("sts3215")) return PART_COLORS.secondary; // motors
  if (f.includes("gripper") || f.includes("moving_jaw") || f.includes("wrist"))
    return PART_COLORS.accent;
  if (
    f.includes("base") ||
    f.includes("waveshare") ||
    f.includes("mounting") ||
    f.includes("motor_holder")
  )
    return PART_COLORS.base;
  return PART_COLORS.primary; // upper/under arm, rotation pitch, etc.
}

// Load a fresh SO-101 instance with STL meshes coloured by role.
// Imperative (no useLoader/Suspense) so each viewer owns its own robot and
// nothing can hang the render tree.
export function useSO101(): URDFRobot | null {
  const [robot, setRobot] = useState<URDFRobot | null>(null);
  useEffect(() => {
    let cancelled = false;
    const loader = new URDFLoader();
    loader.loadMeshCb = (path, manager, done) => {
      if (path.split(".").pop()?.toLowerCase() === "stl") {
        new STLLoader(manager).load(path, (geometry) => {
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(
            geometry,
            new THREE.MeshStandardMaterial({
              color: colorFor(path),
              metalness: 0.3,
              roughness: 0.55,
            }),
          );
          done(mesh);
        });
      } else {
        done(undefined as unknown as THREE.Object3D);
      }
    };
    loader.load(URDF_URL, (r) => {
      if (!cancelled) setRobot(r as unknown as URDFRobot);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return robot;
}

export default function RobotArm({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  const robot = useSO101();

  useEffect(() => {
    if (!robot) return;
    for (const [name, value] of Object.entries(jointValues)) {
      if (typeof robot.setJointValue === "function") robot.setJointValue(name, value);
    }
  }, [robot, jointValues]);

  if (!robot) return null;
  // URDF is Z-up; rotate into three's Y-up world
  return <primitive object={robot} rotation={[-Math.PI / 2, 0, 0]} />;
}
