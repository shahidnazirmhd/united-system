import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Kept in sync with tsconfig.app.json's "paths" — this is the alias
      // Vite's bundler actually resolves at build/dev time; the tsconfig
      // entry is what makes the editor/type-checker agree with it.
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    open: false,
  },
  preview: {
    port: 4173,
  },
});
