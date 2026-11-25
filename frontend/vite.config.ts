import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

// Development only: `npm run dev` forwards /api/* to the local FastAPI backend.
// The target can be changed with VITE_API_PROXY_TARGET (frontend/.env.local).
// Production builds do not use this proxy (Vercel routes /api to the backend).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_")
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": env.VITE_API_PROXY_TARGET || "http://localhost:8000",
      },
    },
  }
})
