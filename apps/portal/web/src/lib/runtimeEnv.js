function readRuntimeValue(key) {
  if (typeof globalThis === "undefined") return undefined
  const runtimeConfig = globalThis.__APP_CONFIG__
  if (!runtimeConfig || typeof runtimeConfig !== "object") return undefined
  return runtimeConfig[key]
}

function readViteValue(key) {
  if (typeof import.meta === "undefined" || !import.meta.env) return undefined
  return import.meta.env[key]
}

function readProcessValue(key) {
  if (typeof process === "undefined" || !process.env) return undefined
  return process.env[key]
}

export function readEnvValue(...keys) {
  for (const key of keys) {
    if (!key) continue
    for (const readValue of [readRuntimeValue, readViteValue, readProcessValue]) {
      const value = readValue(key)
      if (typeof value === "string" && value.trim()) return value.trim()
    }
  }
  return undefined
}
