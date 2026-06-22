"use client";

// „Neue Session"-Dialog: Projekt-Pfad, Initial-Prompt, Modell (Haiku/Sonnet/Opus),
// Permission-Modus. Modell wird bei Erstellung an POST /sessions durchgereicht.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, createSession } from "@/lib/api";
import type { ModelName, PermissionMode } from "@/lib/types";
import { useSessions } from "./sessions-provider";

export function NewSessionDialog({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [projectPath, setProjectPath] = useState("/home/dev/projects/");
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState<ModelName>("sonnet");
  const [mode, setMode] = useState<PermissionMode>("default");

  const valid = projectPath.trim().length > 0 && prompt.trim().length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const session = await createSession({
        project_path: projectPath.trim(),
        initial_prompt: prompt.trim(),
        model,
        permission_mode: mode,
      });
      toast.success("Session gestartet");
      setOpen(false);
      setPrompt("");
      refresh();
      router.push(`/sessions/${session.session_id}`);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Session konnte nicht gestartet werden";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* Base UI: eigenes Element via render (kein asChild wie bei Radix). */}
      <DialogTrigger render={children as React.ReactElement} />
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Neue Session</DialogTitle>
            <DialogDescription>
              Startet eine Claude-Code-Session im gewählten Projekt.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="project_path">Projekt-Pfad</Label>
              <Input
                id="project_path"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/home/dev/projects/jupiter"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="initial_prompt">Initial-Prompt</Label>
              <Textarea
                id="initial_prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Was soll die Session tun?"
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="model">Modell</Label>
                <Select value={model} onValueChange={(v) => setModel(v as ModelName)}>
                  <SelectTrigger id="model">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="haiku">Haiku</SelectItem>
                    <SelectItem value="sonnet">Sonnet</SelectItem>
                    <SelectItem value="opus">Opus</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="mode">Berechtigung</Label>
                <Select value={mode} onValueChange={(v) => setMode(v as PermissionMode)}>
                  <SelectTrigger id="mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Standard</SelectItem>
                    <SelectItem value="acceptEdits">Edits automatisch</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="submit" disabled={!valid || submitting}>
              {submitting ? "Startet…" : "Session starten"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
