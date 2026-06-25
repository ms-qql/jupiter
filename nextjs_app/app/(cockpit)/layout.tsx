import { SessionsProvider } from "@/components/cockpit/sessions-provider";
import { SidebarPrefsProvider } from "@/components/cockpit/sidebar-prefs-provider";
import { CockpitShell } from "@/components/cockpit/cockpit-shell";

export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionsProvider>
      <SidebarPrefsProvider>
        <CockpitShell>{children}</CockpitShell>
      </SidebarPrefsProvider>
    </SessionsProvider>
  );
}
