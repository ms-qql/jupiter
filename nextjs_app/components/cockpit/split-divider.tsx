"use client";

// PROJ-78: Ziehbare, tastaturbedienbare Trennlinie zwischen den beiden
// Arbeitsflächen des Workspace. Setzt während des Ziehens die CSS-Variable
// `--split` auf dem Container (sub-frame-glatt, keine React-Rerenders) und
// committet den Wert erst beim Loslassen an setSplitRatio.

import { useCallback, useEffect, useRef } from "react";
import { SPLIT_MAX, SPLIT_MIN } from "./workspace-provider";

const KEY_STEP = 0.05; // 5% pro Pfeiltaste
const RESET_RATIO = 0.5;

export function SplitDivider({
  containerRef,
  ratio,
  onChange,
  onCommit,
  ariaLabel = "Arbeitsflächen-Trennlinie",
}: {
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** Live-Position (0..1). Wird nur außerhalb des Ziehens gelesen. */
  ratio: number;
  /** Setzt die Position während des Ziehens (CSS-Variable). */
  onChange: (r: number) => void;
  /** Übergibt den Endwert an den State (beim Loslassen / nach Tastatur). */
  onCommit: (r: number) => void;
  ariaLabel?: string;
}) {
  const dragging = useRef(false);

  const clamp = useCallback((r: number) => {
    if (Number.isNaN(r)) return ratio;
    return Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, r));
  }, [ratio]);

  const updateFromClientX = useCallback((clientX: number) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const r = clamp((clientX - rect.left) / rect.width);
    onChange(r);
  }, [containerRef, clamp, onChange]);

  // Maus + Touch (passive: false, damit preventDefault Scroll verhindert).
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragging.current) return;
      e.preventDefault();
      updateFromClientX(e.clientX);
    }
    function onUp() {
      if (!dragging.current) return;
      dragging.current = false;
      const el = containerRef.current;
      if (!el) return;
      const v = Number(el.style.getPropertyValue("--split"));
      if (Number.isFinite(v) && v > 0) onCommit(v);
    }
    function onTouchMove(e: TouchEvent) {
      if (!dragging.current) return;
      const t = e.touches[0];
      if (!t) return;
      e.preventDefault();
      updateFromClientX(t.clientX);
    }
    function onTouchEnd() {
      if (!dragging.current) return;
      dragging.current = false;
      const el = containerRef.current;
      if (!el) return;
      const v = Number(el.style.getPropertyValue("--split"));
      if (Number.isFinite(v) && v > 0) onCommit(v);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [containerRef, updateFromClientX, onCommit]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    let next: number | null = null;
    switch (e.key) {
      case "ArrowLeft":
      case "ArrowUp":
        next = clamp(ratio - KEY_STEP);
        break;
      case "ArrowRight":
      case "ArrowDown":
        next = clamp(ratio + KEY_STEP);
        break;
      case "Home":
        next = SPLIT_MIN;
        break;
      case "End":
        next = SPLIT_MAX;
        break;
      default:
        return;
    }
    e.preventDefault();
    onChange(next);
    onCommit(next);
  };

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label={ariaLabel}
      aria-valuemin={Math.round(SPLIT_MIN * 100)}
      aria-valuemax={Math.round(SPLIT_MAX * 100)}
      aria-valuenow={Math.round(ratio * 100)}
      onKeyDown={onKeyDown}
      onMouseDown={(e) => {
        e.preventDefault();
        dragging.current = true;
        updateFromClientX(e.clientX);
      }}
      onTouchStart={(e) => {
        const t = e.touches[0];
        if (!t) return;
        dragging.current = true;
        updateFromClientX(t.clientX);
      }}
      onDoubleClick={() => {
        onChange(RESET_RATIO);
        onCommit(RESET_RATIO);
      }}
      title="Ziehen zum Teilen · Doppelpfeil-Tasten oder Doppelklick zum Zurücksetzen"
      className="group relative z-10 hidden w-1.5 shrink-0 touch-none cursor-col-resize bg-border transition-colors hover:bg-primary/40 focus-visible:bg-primary/40 focus-visible:outline-none md:block"
    >
      {/* Größere Trefferfläche (5px) ohne den sichtbaren 6px-Strich zu verbreitern. */}
      <div className="pointer-events-none absolute inset-y-0 -left-1 -right-1" />
    </div>
  );
}
