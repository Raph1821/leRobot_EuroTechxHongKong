"use client";

import { useEffect, useMemo } from "react";
import { useLoader } from "@react-three/fiber";
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

// Set up the STL mesh loader + per-role colouring. Shared by the full viewer
// and the mini preview so both look identical.
export function configureURDFLoader(loader: URDFLoader) {
  loader.loadMeshCb = (path, manager, done) => {
    const ext = path.split(".").pop()?.toLowerCase();
    if (ext === "stl") {
      new STLLoader(manager).load(
        path,
        (geometry) => {
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(
            geometry,
            new THREE.MeshStandardMaterial({
              color: colorFor(path),
              metalness: 0.3,
              roughness: 0.55,
            }),
          );
          mesh.userData.srcFile = path;
          done(mesh);
        },
        undefined,
        (err) => done(undefined as unknown as THREE.Object3D, err as Error),
      );
    } else {
      done(undefined as unknown as THREE.Object3D);
    }
  };
}

export default function RobotArm({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  // urdf-loader bundles its own (older) three typings, so its constructor
  // doesn't structurally match r3f's LoaderLike — cast through unknown.
  const robot = useLoader(
    URDFLoader as unknown as new () => THREE.Loader,
    URDF_URL,
    (loader) => configureURDFLoader(loader as unknown as URDFLoader),
  ) as unknown as URDFRobot;

  // colour each part by role (useLoader caches the robot, so do it on the live tree)
  useEffect(() => {
    if (!robot) return;
    robot.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if ((mesh as THREE.Mesh).isMesh) {
        const src = (mesh.userData?.srcFile as string) ?? "";
        const mat = mesh.material as THREE.MeshStandardMaterial;
        mat.color.set(colorFor(src));
        mat.needsUpdate = true;
      }
    });
  }, [robot]);

  // apply joint angles whenever they change
  useEffect(() => {
    if (!robot) return;
    for (const [name, value] of Object.entries(jointValues)) {
      robot.setJointValue(name, value);
    }
  }, [robot, jointValues]);

  // URDF is Z-up; rotate into three's Y-up world and drop onto the ground
  const transform = useMemo(() => ({ rotation: [-Math.PI / 2, 0, 0] as const }), []);

  return <primitive object={robot} rotation={transform.rotation} />;
}
