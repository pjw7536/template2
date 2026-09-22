import { mkdirSync, writeFileSync } from "node:fs"
import { dirname } from "node:path"
import process from "node:process"

const DEFAULT_OUTPUT_PATH = "/app/dist/runtime-env.js"
const NON_VITE_RUNTIME_KEYS = new Set([
  "BACKEND_API_URL",
  "BACKEND_URL",
  "MINIO_ENDPOINT",
])

const runtimeConfig = Object.fromEntries(
  Object.entries(process.env)
    .filter(([key]) => key.startsWith("VITE_") || NON_VITE_RUNTIME_KEYS.has(key))
    .sort(([left], [right]) => left.localeCompare(right)),
)

const outputPath = process.env.RUNTIME_ENV_OUTPUT_PATH || DEFAULT_OUTPUT_PATH
const content = `globalThis.__APP_CONFIG__ = Object.freeze(${JSON.stringify(runtimeConfig)});\n`

mkdirSync(dirname(outputPath), { recursive: true })
writeFileSync(outputPath, content, "utf8")
