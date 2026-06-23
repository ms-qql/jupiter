"use client";

// „Mit Handover frisch neu starten" (PROJ-5): archiviert die alte Session und startet
// eine Kind-Session, die NUR den verdichteten Handover als Startkontext (Seed) bekommt
// — bewusst kein --resume (das schleppt den vollen alten Kontext mit). Staffelstab.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCcwIcon } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, generateHandover, resetSession } from "@/lib/api";

export function ResetSessionButton({
  sessionId,
  numTurns,
}: {
  sessionId: string;
  numTurns: number;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [seed, setSeed] = useState("");

  // Edge-Case „Reset bei sehr kurzer Session": erlaubt, aber Hinweis.
  const lowContext = numTurns <= 1;

  async function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) return;
    setLoading(true);
    try {
      const preview = await generateHandover(sessionId);
      setSeed(preview.body);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Handover-Generierung fehlgeschlagen");
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleReset() {
    if (!seed.trim() || resetting) return;
    setResetting(true);
    try {
      const child = await resetSession(sessionId, seed);
      toast.success("Frische Session mit Handover gestartet");
      setOpen(false);
      router.push(`/sessions/${child.session_id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Zurücksetzen fehlgeschlagen");
    } finally {
      setResetting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <RotateCcwIcon className="size-4" />
            Zurücksetzen
          </Button>
        }
      />
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Session zurücksetzen</DialogTitle>
          <DialogDescription>
            Archiviert die aktuelle Session und startet eine frische Kind-Session, die nur
            diesen verdichteten Handover als Startkontext erhält. Der alte Kontext wird
            bewusst NICHT mitgeschleppt.
          </DialogDescription>
        </DialogHeader>

        {lowContext && (
          <p className="rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-xs text-amber-500">
            Wenig Kontext: Diese Session hatte kaum Turns — ein Reset lohnt sich meist erst
            bei vollem Kontextfenster.
          </p>
        )}

        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Generiere Seed-Kontext…
          </p>
        ) : (
          <div className="grid gap-2 py-2">
            <Textarea
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              rows={12}
              className="font-mono text-xs"
              aria-label="Seed-Kontext (Handover)"
            />
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button onClick={handleReset} disabled={loading || resetting || !seed.trim()}>
            {resetting ? "Startet…" : "Archivieren & frisch starten"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
