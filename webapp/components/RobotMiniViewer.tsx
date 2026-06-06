"use client";

import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Center, OrbitControls } from "@react-three/drei";
import RobotMini from "./RobotMini";
import type { JointValues } from "@/lib/joints";

export default function RobotMiniViewer({
  jointValues,
}: {
  jointValues: JointValues;
}) {
  return (
    <Canvas
      camera={{ position: [0.45, 0.35, 0.55], fov: 42, near: 0.01, far: 50 }}
      dpr={[1, 1.5]}
    >
      <color attach="background" args={["#eceae2"]} />
      <hemisphereLight intensity={0.9} groundColor="#eceae2" color="#ffffff" />
      <directionalLight position={[2, 4, 2]} intensity={2} />
      <directionalLight position={[-2, 2, -1]} intensity={0.7} />
      <Suspense fallback={null}>
        <Center>
          <RobotMini jointValues={jointValues} />
        </Center>
      </Suspense>
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={1.1}
      />
    </Canvas>
  );
}
