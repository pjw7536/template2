import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "node:path"
import process from "node:process"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(process.cwd(), "src"),
      components: path.resolve(process.cwd(), "src/components"),
    },
  },
  server: {
    host: true,
    port: 3000,
    allowedHosts: ["stg.plane.samsungds.net"],
    hmr: {
      host: "stg.plane.samsungds.net",
      protocol: "wss",
      clientPort: 443,
    },
  },

})
