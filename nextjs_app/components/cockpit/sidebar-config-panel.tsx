"use client";

// PROJ-38: Konfig-Panel hinter dem Einstellungs-Icon der „Workspace"-Überschrift.
// Pro Eintrag: Sichtbarkeit (Auge), Reihenfolge (Drag + ▲/▼-Fallback für Touch),
// dazu RESET. Zugang ist bewusst NIE ausblendbar (kein Aussperren).

import { useState } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  EyeIcon,
  EyeOffIcon,
  GripVerticalIcon,
  RotateCcwIcon,
  Settings2Icon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { SIDEBAR_SECTIONS } from "@/lib/sidebar-config";
import { useSidebarPrefs, type ResolvedItem } from "./sidebar-prefs-provider";

export function SidebarConfigButton() {
  const { allItems, toggleVisible, move, reorder, reset, mounted } =
    useSidebarPrefs();
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [overKey, setOverKey] = useState<string | null>(null);

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="Sidebar anpassen"
            title="Sidebar anpassen"
            className="text-muted-foreground hover:text-foreground"
          />
        }
      >
        <Settings2Icon />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="mb-1 font-heading text-sm font-medium leading-none">
          Sidebar anpassen
        </div>
        <p className="mb-2.5 text-xs text-muted-foreground">
          Ziehen zum Sortieren · Auge zum Ausblenden
        </p>

        {/* mounted-Guard: vor dem localStorage-Read keine evtl. falsche Reihenfolge */}
        {mounted &&
          SIDEBAR_SECTIONS.map((section) => {
            const items = allItems(section.id);
            if (items.length === 0) return null;
            return (
              <div key={section.id} className="mb-2 last:mb-0">
                <div className="px-1 pb-1 text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
                  {section.label}
                </div>
                <div className="flex flex-col gap-0.5">
                  {items.map((item, i) => (
                    <ConfigRow
                      key={item.key}
                      item={item}
                      isFirst={i === 0}
                      isLast={i === items.length - 1}
                      isDragging={dragKey === item.key}
                      isOver={overKey === item.key && dragKey !== item.key}
                      onToggle={() => toggleVisible(item.key)}
                      onMove={(dir) => move(item.key, dir)}
                      onDragStart={() => setDragKey(item.key)}
                      onDragEnter={() => setOverKey(item.key)}
                      onDragEnd={() => {
                        setDragKey(null);
                        setOverKey(null);
                      }}
                      onDrop={() => {
                        if (dragKey) reorder(dragKey, item.key);
                        setDragKey(null);
                        setOverKey(null);
                      }}
                    />
                  ))}
                </div>
              </div>
            );
          })}

        <div className="mt-3 border-t border-border pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={reset}
            className="w-full justify-start text-muted-foreground hover:text-foreground"
          >
            <RotateCcwIcon />
            Auf Standard zurücksetzen
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function ConfigRow({
  item,
  isFirst,
  isLast,
  isDragging,
  isOver,
  onToggle,
  onMove,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onDrop,
}: {
  item: ResolvedItem;
  isFirst: boolean;
  isLast: boolean;
  isDragging: boolean;
  isOver: boolean;
  onToggle: () => void;
  onMove: (dir: -1 | 1) => void;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  onDrop: () => void;
}) {
  const Icon = item.icon;
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragEnd={onDragEnd}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-1 py-1 transition-colors",
        isDragging && "opacity-40",
        isOver && "bg-accent/60 ring-1 ring-ring/40",
        !isOver && "hover:bg-accent/40",
      )}
    >
      <GripVerticalIcon className="size-3.5 shrink-0 cursor-grab text-muted-foreground/60 active:cursor-grabbing" />
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-sm",
          !item.visible && "text-muted-foreground line-through",
        )}
      >
        {item.label}
      </span>
      {/* ▲/▼ — Touch-Fallback fürs Sortieren */}
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={`${item.label} nach oben`}
        disabled={isFirst}
        onClick={() => onMove(-1)}
        className="text-muted-foreground hover:text-foreground"
      >
        <ArrowUpIcon />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={`${item.label} nach unten`}
        disabled={isLast}
        onClick={() => onMove(1)}
        className="text-muted-foreground hover:text-foreground"
      >
        <ArrowDownIcon />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={item.visible ? `${item.label} ausblenden` : `${item.label} einblenden`}
        aria-pressed={item.visible}
        onClick={onToggle}
        className={cn(
          item.visible
            ? "text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        {item.visible ? <EyeIcon /> : <EyeOffIcon />}
      </Button>
    </div>
  );
}
