"use client";

import { useRouter } from "next/navigation";
import { ACCOUNTS, ROLE_LABELS, useRole, type Role } from "@/lib/role";

// Simulated sign-in screen (beta, no real auth). Shown after "Log out".
export default function AccountGate({ children }: { children: React.ReactNode }) {
  const { signedOut, signIn } = useRole();
  const router = useRouter();

  if (!signedOut) return <>{children}</>;

  const pick = (r: Role) => {
    signIn(r);
    router.push(r === "patient" ? "/" : "/patients");
  };

  return (
    <div className="grid h-screen place-items-center bg-paper text-ink">
      <div className="w-full max-w-sm px-6">
        <div className="mb-8 text-center">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-ink text-lg font-bold text-paper">
            E
          </span>
          <h1 className="font-display mt-4 text-2xl font-extrabold tracking-tight">
            Elda
          </h1>
          <p className="mt-1 text-sm text-ink-soft">Choose an account to continue</p>
        </div>

        <div className="space-y-2">
          {ACCOUNTS.map((a) => (
            <button
              key={a.role}
              onClick={() => pick(a.role)}
              className="flex w-full items-center gap-3 rounded-2xl border border-hairline bg-paper p-4 text-left transition-all hover:-translate-y-0.5 hover:border-ink/30 hover:shadow-[0_12px_40px_-20px_rgba(14,17,22,0.4)]"
            >
              <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-paper-2 text-sm font-bold">
                {a.initials}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{a.name}</span>
                <span className="text-xs uppercase tracking-wider text-ink-soft">
                  {ROLE_LABELS[a.role]}
                </span>
              </span>
            </button>
          ))}
        </div>

        <p className="mt-6 text-center text-[11px] text-ink-soft">
          Beta · simulated accounts, no password required
        </p>
      </div>
    </div>
  );
}
