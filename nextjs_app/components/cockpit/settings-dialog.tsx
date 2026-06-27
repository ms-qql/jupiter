"use client";

// Cockpit-Einstellungen — bündelt globale Regler in Tabs:
//  - Allgemein (PROJ-5): Kontext-Schwelle für Warnung + Handover-Vorschlag.
//  - Trust-Policy (PROJ-10): abgestuftes Vertrauen + Phasen-Übergangs-Gate.
//  - Watchdog (PROJ-16): Reißleine — Token-/Zeit-/Wiederholungs-/Schreib-Limits.
//  - Liveness (PROJ-27): verifizierter Heartbeat + Auto-Reanimierung hängender Sessions.
//  - Sprache (PROJ-20): Quelle der Push-to-Talk-Transkription (lokal/Groq).
// Über das Zahnrad im Mission-Control-Header.

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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ThresholdControl } from "./threshold-control";
import { PolicyControl } from "./policy-control";
import { WatchdogControl } from "./watchdog-control";
import { LivenessControl } from "./liveness-control";
import { TranscriptionControl } from "./transcription-control";
import { RegistryControl } from "./registry-control";
import { EngineModelsControl } from "./engine-models-control";

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
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Einstellungen</DialogTitle>
          <DialogDescription>
            Globale Defaults für alle Sessions. Pro Session überschreibbar.
          </DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="allgemein">
          <TabsList>
            <TabsTrigger value="allgemein">Allgemein</TabsTrigger>
            <TabsTrigger value="policy">Trust-Policy</TabsTrigger>
            <TabsTrigger value="watchdog">Watchdog</TabsTrigger>
            <TabsTrigger value="liveness">Liveness</TabsTrigger>
            <TabsTrigger value="sprache">Sprache</TabsTrigger>
            <TabsTrigger value="modelle">Modelle</TabsTrigger>
            <TabsTrigger value="registry">Registry</TabsTrigger>
          </TabsList>
          <TabsContent value="allgemein" className="py-2">
            <ThresholdControl />
          </TabsContent>
          <TabsContent value="policy" className="py-2">
            <ScrollArea className="max-h-[60vh] pr-3">
              <PolicyControl />
            </ScrollArea>
          </TabsContent>
          <TabsContent value="watchdog" className="py-2">
            <ScrollArea className="max-h-[60vh] pr-3">
              <WatchdogControl />
            </ScrollArea>
          </TabsContent>
          <TabsContent value="liveness" className="py-2">
            <ScrollArea className="max-h-[60vh] pr-3">
              <LivenessControl />
            </ScrollArea>
          </TabsContent>
          <TabsContent value="sprache" className="py-2">
            <TranscriptionControl />
          </TabsContent>
          <TabsContent value="modelle" className="py-2">
            <ScrollArea className="max-h-[60vh] pr-3">
              <EngineModelsControl />
            </ScrollArea>
          </TabsContent>
          <TabsContent value="registry" className="py-2">
            <ScrollArea className="max-h-[60vh] pr-3">
              <RegistryControl />
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
