"use client";

// Ziehbare Breite für die Datei-Spalten (Doku + Dateien). Breite pro `storageKey`
// in localStorage gemerkt, damit die Spalte nach dem Lesen breit bleibt.

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

const MIN = 200;
const MAX = 720;

export function ResizableAside({
  storageKey,
  defaultWidth,
  className,
  children,
  ...rest
}: React.ComponentProps<"aside"> & { storageKey: string; defaultWidth: number }) {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const saved = Number(localStorage.getItem(storageKey));
    if (saved >= MIN && saved <= MAX) setWidth(saved);
  }, [storageKey]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragging.current) return;
      e.preventDefault();
      setWidth(Math.min(MAX, Math.max(MIN, e.clientX - (ref.current?.getBoundingClientRect().left ?? 0))));
    }
    function onUp() {
      if (!dragging.current) return;
      dragging.current = false;
      localStorage.setItem(storageKey, String(width));
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [storageKey, width]);

  return (
    <aside
      ref={ref}
      // Breite nur ab md — mobil bleibt die Spalte voll breit (w-full via className).
      style={{ ["--aside-w" as string]: `${width}px` }}
      className={cn("relative shrink-0 md:w-[var(--aside-w)]", className)}
      {...rest}
    >
      {children}
      {/* Griff: sitzt auf der rechten Kante, 8px Trefferfläche */}
      <div
        onMouseDown={() => {
          dragging.current = true;
        }}
        onDoubleClick={() => {
          setWidth(defaultWidth);
          localStorage.setItem(storageKey, String(defaultWidth));
        }}
        title="Breite ziehen (Doppelklick: zurücksetzen)"
        className="absolute inset-y-0 -right-1 z-10 hidden w-2 cursor-col-resize hover:bg-primary/30 md:block"
      />
    </aside>
  );
}
