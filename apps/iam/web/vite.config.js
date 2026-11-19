import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "node:path"

const proxy = { "/api/workload": process.env.IAM_WORKLOAD_API_TARGET || "http://127.0.0.1:5175" }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: { host: true, port: 5174, strictPort: true, proxy },
  preview: { proxy },
  test: { environment: "node" },
})
