"use client";

import { FileExplorer } from "@/components/cockpit/file-explorer";

// PROJ-28: Drei-Spalten-Layout (Sidebar via CockpitShell · Datei-Panel · Ansicht)
// — das volle Layout liegt in FileExplorer, analog zum Doku-Reader (PROJ-7).
export default function DateienPage() {
  return <FileExplorer />;
}
