"use client";

// PROJ-25: schützt die Cockpit-Routen. Solange der AuthProvider prüft → Loader;
// anonym → weich auf /login (mit ?next=) umleiten; angemeldet → Inhalt zeigen.
// Die harte Umleitung in api.ts greift zusätzlich bei mitten-drin abgelaufenen
// Tokens; hier geht es um den sauberen Erstzugang.

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2Icon } from "lucide-react";
import { useAuth } from "./auth-provider";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anon") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, pathname, router]);

  if (status === "authed") return <>{children}</>;

  return (
    <div className="flex h-dvh items-center justify-center text-muted-foreground">
      <Loader2Icon className="size-5 animate-spin" aria-label="Wird geladen" />
    </div>
  );
}
