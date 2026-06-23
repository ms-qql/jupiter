// Kleiner Helfer: Text in die Zwischenablage kopieren (für „Pfad kopieren").
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
