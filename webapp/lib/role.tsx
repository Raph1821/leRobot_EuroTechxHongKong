"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Role = "patient" | "nurse" | "doctor";

export const ROLE_LABELS: Record<Role, string> = {
  patient: "Patient",
  nurse: "Nurse",
  doctor: "Doctor",
};

// Beta: simulated accounts, no real auth. One account per role.
export type Account = { role: Role; name: string; initials: string };

export const ACCOUNTS: Account[] = [
  { role: "patient", name: "Mei-Ling Chan", initials: "MC" },
  { role: "nurse", name: "Yuki Nakamura", initials: "YN" },
  { role: "doctor", name: "Dr. Wei Lin", initials: "WL" },
];

export const accountFor = (role: Role): Account =>
  ACCOUNTS.find((a) => a.role === role) ?? ACCOUNTS[0];

const PERMS = {
  patient: { managePatients: false, prescribe: false, markDose: false, ackAlerts: false },
  nurse: { managePatients: true, prescribe: false, markDose: true, ackAlerts: true },
  doctor: { managePatients: true, prescribe: true, markDose: true, ackAlerts: true },
} as const;

export type Perms = (typeof PERMS)[Role];

type RoleCtx = {
  role: Role;
  account: Account;
  can: Perms;
  signedOut: boolean;
  signIn: (r: Role) => void;
  signOut: () => void;
};

const Ctx = createContext<RoleCtx | null>(null);

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<Role>("patient");
  const [signedOut, setSignedOut] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("elda-role") as Role | null;
    if (saved && saved in PERMS) setRoleState(saved);
  }, []);

  const signIn = (r: Role) => {
    setRoleState(r);
    setSignedOut(false);
    try {
      localStorage.setItem("elda-role", r);
    } catch {
      /* ignore */
    }
  };

  const signOut = () => setSignedOut(true);

  return (
    <Ctx.Provider
      value={{
        role,
        account: accountFor(role),
        can: PERMS[role],
        signedOut,
        signIn,
        signOut,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useRole(): RoleCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useRole must be used within RoleProvider");
  return c;
}
