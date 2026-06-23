"use client";

import { FileExplorer } from "@/components/cockpit/file-explorer";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";

export default function DateienPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Dateien</h1>
          <p className="text-sm text-muted-foreground">
            Dateien browsen, hochladen (auch per Einfügen) und Pfade kopieren.
          </p>
        </div>
        <ThemeToggle />
      </header>
      <FileExplorer />
    </div>
  );
}
