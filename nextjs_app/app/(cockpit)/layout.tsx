import { SessionsProvider } from "@/components/cockpit/sessions-provider";
import { SessionRail } from "@/components/cockpit/session-rail";

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionsProvider>
      <div className="flex h-dvh overflow-hidden">
        <SessionRail />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </SessionsProvider>
  );
}
