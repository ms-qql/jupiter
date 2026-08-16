import { SessionsProvider } from "@/components/cockpit/sessions-provider";
import { SidebarPrefsProvider } from "@/components/cockpit/sidebar-prefs-provider";
import { WorkspaceProvider } from "@/components/cockpit/workspace-provider";
import { CockpitShell } from "@/components/cockpit/cockpit-shell";
import { AuthGate } from "@/components/auth/auth-gate";

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGate>
      <SessionsProvider>
        <SidebarPrefsProvider>
          <WorkspaceProvider>
            <CockpitShell>{children}</CockpitShell>
          </WorkspaceProvider>
        </SidebarPrefsProvider>
      </SessionsProvider>
    </AuthGate>
  );
}
