"use client";

// PROJ-25: öffentliche Login-Seite (außerhalb der AuthGate). Zwei Modi:
//  • normaler Login (Username + Passwort)
//  • Bootstrap (erster Account) — nur solange die Nutzerbasis leer ist.
// Bei bereits angemeldetem Zustand leitet die Seite direkt auf ?next= weiter.

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2Icon } from "lucide-react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function safeNext(raw: string | null): string {
  // Nur app-interne Pfade zulassen (kein Open-Redirect über //host o. Ä.).
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  if (raw.startsWith("/login")) return "/";
  return raw;
}

function LoginForm() {
  const { status, signIn, signUpFirst, bootstrapNeeded } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Schon angemeldet (z. B. via Refresh-Cookie) → raus aus dem Login.
  useEffect(() => {
    if (status === "authed") router.replace(next);
  }, [status, next, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (bootstrapNeeded && password !== confirm) {
      setError("Die Passwörter stimmen nicht überein.");
      return;
    }
    setBusy(true);
    try {
      if (bootstrapNeeded) await signUpFirst(username.trim(), password);
      else await signIn(username.trim(), password);
      router.replace(next);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Anmeldung fehlgeschlagen. Bitte erneut versuchen.",
      );
      setBusy(false);
    }
  }

  if (status === "loading") {
    return (
      <Loader2Icon
        className="size-5 animate-spin text-muted-foreground"
        aria-label="Wird geladen"
      />
    );
  }

  const title = bootstrapNeeded ? "Konto einrichten" : "Anmelden";
  const description = bootstrapNeeded
    ? "Noch kein Konto vorhanden — lege das erste an, um Jupiter zu nutzen."
    : "Melde dich an, um deine Sessions und Wissensnotizen zu sehen.";

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle className="text-base">🛰️ Jupiter · {title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="username">Benutzername</Label>
            <Input
              id="username"
              name="username"
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={busy}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Passwort</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete={bootstrapNeeded ? "new-password" : "current-password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
          </div>
          {bootstrapNeeded && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm">Passwort bestätigen</Label>
              <Input
                id="confirm"
                name="confirm"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={busy}
              />
            </div>
          )}
          {error && (
            <p role="alert" className="text-xs text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy} className="mt-1">
            {busy && <Loader2Icon className="size-4 animate-spin" />}
            {bootstrapNeeded ? "Konto anlegen" : "Anmelden"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4">
      <Suspense
        fallback={
          <Loader2Icon
            className="size-5 animate-spin text-muted-foreground"
            aria-label="Wird geladen"
          />
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}
