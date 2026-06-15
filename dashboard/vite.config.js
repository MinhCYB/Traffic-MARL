// dashboard/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/logs":    "http://localhost:8000",
      "/command": "http://localhost:8000",
      "/status":  "http://localhost:8000",
      "/data":    "http://localhost:8000",
      "/ws": {
        target:          "ws://localhost:8000",
        ws:              true,
        rewriteWsOrigin: true,
      },
    },
  },
});