"use client";

// PROJ-21: Gemeinsame Datenquelle für Portfolio- und Assembler-Tab. Liest den
// Registry-Katalog bzw. die Branding-Profile aus dem Backend-Vertrag
// (GET /ui-check/registry, GET /ui-check/branding-profiles). Keine eigene
// Registry-/Branding-Logik im Frontend — nur Laden, Fehlerbehandlung, Cache.

import { useEffect, useState } from "react";
import {
  ApiError,
  getUiCheckBrandingProfiles,
  getUiCheckRegistry,
} from "@/lib/api";
import type {
  UiCheckBrandingProfileSummary,
  UiCheckRegistryItem,
} from "@/lib/types";

interface RegistryState {
  items: UiCheckRegistryItem[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useUiCheckRegistry(): RegistryState {
  const [items, setItems] = useState<UiCheckRegistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    getUiCheckRegistry(ctrl.signal)
      .then((res) => {
        setItems(res.items);
        setError(null);
      })
      .catch((err) => {
        if (ctrl.signal.aborted) return;
        setItems([]);
        setError(
          err instanceof ApiError
            ? `${err.message} (Quelle: GET /ui-check/registry → registry/registry.json)`
            : "Registry-Katalog ist nicht erreichbar (registry/registry.json).",
        );
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [reloadKey]);

  return {
    items,
    loading,
    error,
    reload: () => {
      setLoading(true);
      setReloadKey((k) => k + 1);
    },
  };
}

interface BrandingProfilesState {
  profiles: UiCheckBrandingProfileSummary[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useUiCheckBrandingProfiles(): BrandingProfilesState {
  const [profiles, setProfiles] = useState<UiCheckBrandingProfileSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    getUiCheckBrandingProfiles(ctrl.signal)
      .then((res) => {
        setProfiles(res.profiles);
        setError(null);
      })
      .catch((err) => {
        if (ctrl.signal.aborted) return;
        setProfiles([]);
        setError(
          err instanceof ApiError
            ? `${err.message} (Quelle: GET /ui-check/branding-profiles → branding/<slug>/)`
            : "Branding-Profile sind nicht erreichbar (branding/<slug>/).",
        );
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [reloadKey]);

  return {
    profiles,
    loading,
    error,
    reload: () => {
      setLoading(true);
      setReloadKey((k) => k + 1);
    },
  };
}

/** Katalog-Items, die als Templates/Komponenten/Blocks im Portfolio bzw. als
 *  Auswahl im Assembler sinnvoll sind. `registry:lib`/`registry:style` sind
 *  interne Bausteine (z. B. verdict-lib, verdict-styles) und keine
 *  auswählbaren Sektionen. */
export function isGalleryItem(item: UiCheckRegistryItem): boolean {
  return item.type === "registry:block" || item.type === "registry:template";
}
