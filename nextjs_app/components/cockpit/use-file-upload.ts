"use client";

// Geteilter Upload-Hook für beide Oberflächen (PROJ-11): Fileexplorer (Surface A)
// und In-Session Dokument-Clipboard (Surface B). Ohne targetDir landet der Upload
// im Clipboard-Ordner (Backend-Default).

import { useState } from "react";
import { toast } from "sonner";

import { ApiError, uploadFiles } from "@/lib/api";
import type { FileEntry } from "@/lib/types";

export function useFileUpload(targetDir?: string) {
  const [uploading, setUploading] = useState(false);

  async function upload(files: FileList | File[] | null): Promise<FileEntry[]> {
    const list = files ? Array.from(files) : [];
    if (list.length === 0) return [];
    setUploading(true);
    try {
      const res = await uploadFiles(list, targetDir);
      return res.files;
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload fehlgeschlagen");
      return [];
    } finally {
      setUploading(false);
    }
  }

  return { upload, uploading };
}
