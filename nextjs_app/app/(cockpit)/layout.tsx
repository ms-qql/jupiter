import { SessionsProvider } from "@/components/cockpit/sessions-provider";
import { CockpitShell } from "@/components/cockpit/cockpit-shell";

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionsProvider>
      <CockpitShell>{children}</CockpitShell>
    </SessionsProvider>
  );
}
