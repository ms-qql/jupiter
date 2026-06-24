// PROJ-27: verifizierter Heartbeat-Indikator — ZUSÄTZLICH zur Status-Ampel (PROJ-3).
// Die Ampel zeigt den Workflow-Status; dieser Punkt zeigt, ob der Prozess WIRKLICH lebt
// und Fortschritt macht (geprüfter Heartbeat) — eine „arbeitet"-Ampel kann lügen, wenn
// die Session in Wahrheit hängt. Bewusst ein Herz-Icon, klar abgesetzt vom runden
// Ampel-Punkt: aktiv = pulsierender Herzschlag (grün), hängt = Riss (amber), tot (grau).

import { HeartCrackIcon, HeartOffIcon, HeartPulseIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { livenessMeta } from "@/lib/status";
import type { Liveness } from "@/lib/types";

const ICON: Record<Liveness, typeof HeartPulseIcon> = {
  aktiv: HeartPulseIcon,
  hängt: HeartCrackIcon,
  tot: HeartOffIcon,
};

const COLOR: Record<LivenessColor, string> = {
  emerald: "text-emerald-500",
  amber: "text-amber-500",
  zinc: "text-zinc-500",
};

type LivenessColor = "emerald" | "amber" | "zinc";

export function HeartbeatDot({
  liveness,
  autoAttempts = 0,
  size = "sm",
  className,
}: {
  liveness: Liveness;
  autoAttempts?: number;
  size?: "sm" | "md";
  className?: string;
}) {
  const meta = livenessMeta(liveness);
  const Icon = ICON[liveness] ?? HeartOffIcon;
  const px = size === "sm" ? "size-3.5" : "size-4";
  const title =
    liveness === "aktiv"
      ? "Aktiv — Prozess lebt und macht Fortschritt (verifizierter Heartbeat)"
      : liveness === "hängt"
        ? `Hängt — Prozess lebt, aber kein Fortschritt${autoAttempts ? ` · ${autoAttempts}× automatisch reanimiert` : ""}`
        : "Beendet/tot — Prozess nicht (mehr) steuerbar";
  return (
    <span
      className={cn("inline-flex shrink-0 items-center", className)}
      title={title}
      aria-label={title}
    >
      <Icon className={cn(px, COLOR[meta.color], meta.pulse && "animate-pulse")} />
    </span>
  );
}
