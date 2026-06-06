"use client";

import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Center } from "@react-three/drei";
import RobotArm from "./RobotArm";
import type { JointValues } from "@/lib/joints";

export default function RobotViewer({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  return (
    <Canvas
      camera={{ position: [0.45, 0.35, 0.55], fov: 42, near: 0.01, far: 50 }}
      dpr={[1, 2]}
    >
      <color attach="background" args={["#f5f4ef"]} />
      <hemisphereLight intensity={0.9} groundColor="#eceae2" color="#ffffff" />
      <directionalLight position={[2, 4, 2]} intensity={2} />
      <directionalLight position={[-2, 3, -1]} intensity={0.8} />
      <Suspense fallback={null}>
        <Center>
          <RobotArm jointValues={jointValues} />
        </Center>
      </Suspense>

      <Grid
        args={[10, 10]}
        cellSize={0.05}
        cellThickness={0.6}
        cellColor="#d6d3c8"
        sectionSize={0.25}
        sectionThickness={1}
        sectionColor="#b9b5a8"
        fadeDistance={4}
        fadeStrength={1.5}
        infiniteGrid
        position={[0, -0.2, 0]}
      />
      <OrbitControls
        makeDefault
        enableDamping
        enablePan={false}
        minDistance={0.2}
        maxDistance={3}
        target={[0, 0.15, 0]}
      />
    </Canvas>
  );
}
