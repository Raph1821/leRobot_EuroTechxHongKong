import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { JointProvider } from "@/lib/jointStore";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <JointProvider>
      <div className="flex h-screen bg-paper text-ink">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="min-h-0 flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </JointProvider>
  );
}
