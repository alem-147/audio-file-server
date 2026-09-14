import { defineConfig } from "vite";

// Port matches the server's default AUDIO_SERVER_FRONTEND_PORT (see
// server/src/server/config.py), which the server's CORS config allows.
export default defineConfig({
  server: {
    port: 3000,
  },
});
