import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Obrigatório para funcionar dentro do container Docker
    host: "0.0.0.0",
    port: 5173,

    // Polling é necessário em ambientes Docker/Linux onde os eventos
    // de filesystem (inotify) podem não ser propagados corretamente
    watch: {
      usePolling: true,
    },

    // Proxy: chamadas para /api/* são redirecionadas ao backend FastAPI
    proxy: {
      "/api": {
        target: "http://api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

