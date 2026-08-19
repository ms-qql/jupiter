"use client";

// Isoliert Abstürze einer nativen, lazy-geladenen Micro-App (React.lazy()) vom
// Rest von Jupiter. Ohne diese Grenze reißt ein fehlgeschlagener Chunk-Load
// (typischer Fall: Deploy tauscht den Build aus, während ein Tab noch offen
// ist — der alte Chunk-Hash existiert nicht mehr) den gesamten React-Baum mit,
// weil <Suspense> nur den Ladezustand abfängt, keine Fehler. Fehlt zusätzlich
// ein app/global-error.tsx, bleibt Jupiter komplett unbedienbar bis zum
// harten Reload. Ein Error Boundary ist die einzige React-API, die das fängt.

import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class MicroAppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6">
          <p className="rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-6 text-sm text-red-400">
            Diese App konnte nicht geladen werden — das passiert typischerweise
            kurz nach einem Deploy, wenn der Browser noch einen alten Stand
            offen hat. Bitte die Seite neu laden.
          </p>
          <Button
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={() => window.location.reload()}
          >
            Neu laden
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
