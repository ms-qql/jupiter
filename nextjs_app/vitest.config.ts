import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Spiegelt den tsconfig-Pfad-Alias "@/*" → Projektwurzel, damit auch Komponenten-
// Tests (die intern @/… importieren) ohne Next.js-Build aufgelöst werden.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
});
