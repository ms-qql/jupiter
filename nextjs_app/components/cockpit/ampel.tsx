import { cn } from "@/lib/utils";
import type { Ampel as AmpelColor } from "@/lib/status";

const COLOR: Record<AmpelColor, string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-400",
  red: "bg-red-500",
  gray: "bg-zinc-500",
};

const PULSE: Record<AmpelColor, boolean> = {
  green: true, // arbeitet → pulsiert
  amber: true, // wartet auf dich → pulsiert (stärkstes Signal)
  red: false,
  gray: false,
};

export function Ampel({
  color,
  size = "md",
  className,
}: {
  color: AmpelColor;
  size?: "sm" | "md";
  className?: string;
}) {
  const px = size === "sm" ? "h-2 w-2" : "h-2.5 w-2.5";
  return (
    <span className={cn("relative inline-flex", px, className)}>
      {PULSE[color] && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
            COLOR[color],
          )}
        />
      )}
      <span
        className={cn(
          "relative inline-flex rounded-full",
          px,
          COLOR[color],
        )}
      />
    </span>
  );
}
