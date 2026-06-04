"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { HOME_POSE, type JointValues } from "./joints";

type JointCtx = {
  values: JointValues;
  setJoint: (name: string, value: number) => void;
  home: () => void;
};

const Ctx = createContext<JointCtx | null>(null);

// Lives in the app shell (which doesn't unmount on route change), so joint
// values are shared live between Manual Control and the Overview cards.
export function JointProvider({ children }: { children: React.ReactNode }) {
  const [values, setValues] = useState<JointValues>({ ...HOME_POSE });
  const setJoint = useCallback(
    (name: string, value: number) =>
      setValues((prev) => ({ ...prev, [name]: value })),
    [],
  );
  const home = useCallback(() => setValues({ ...HOME_POSE }), []);
  return (
    <Ctx.Provider value={{ values, setJoint, home }}>{children}</Ctx.Provider>
  );
}

export function useJoints(): JointCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useJoints must be used within JointProvider");
  return c;
}
