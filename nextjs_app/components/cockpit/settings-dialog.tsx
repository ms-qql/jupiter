"use client";

// Cockpit-Einstellungen (PROJ-5): bündelt globale Regler — aktuell die Kontext-Schwelle
// für Warnung + Handover-Vorschlag. Über das Zahnrad im Mission-Control-Header.

import { SettingsIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ThresholdControl } from "./threshold-control";

export function SettingsDialog() {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button variant="outline" size="icon" aria-label="Einstellungen">
            <SettingsIcon className="size-4" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Einstellungen</DialogTitle>
          <DialogDescription>
            Globale Defaults für alle Sessions. Pro Session überschreibbar.
          </DialogDescription>
        </DialogHeader>
        <div className="py-2">
          <ThresholdControl />
        </div>
      </DialogContent>
    </Dialog>
  );
}
