import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import AccountGate from "./AccountGate";
import { JointProvider } from "@/lib/jointStore";
import { RoleProvider } from "@/lib/role";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RoleProvider>
      <JointProvider>
        <AccountGate>
          <div className="flex h-screen bg-paper text-ink">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar />
              <main className="min-h-0 flex-1 overflow-auto">{children}</main>
            </div>
          </div>
        </AccountGate>
      </JointProvider>
    </RoleProvider>
  );
}
