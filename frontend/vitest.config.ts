import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Separate from vite.config.ts deliberately: keeps test-only configuration
// (environment, setupFiles, coverage) from leaking into the production
// build config, while still sharing the same plugin/alias setup so tests
// resolve "@/..." imports identically to the real app.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setupTests.ts"],
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: ["src/components/ui/**", "src/main.tsx", "**/*.d.ts"],
    },
  },
});
