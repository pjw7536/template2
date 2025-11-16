// src/lib/api.js
const DEFAULT_BACKEND_URL = "http://localhost:8000/"

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

function readEnvValue(...keys) {
  for (const key of keys) {
    if (!key) continue
    if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
      const value = import.meta.env[key]
      if (typeof value === "string" && value.trim()) {
        return value
      }
    }
    if (typeof process !== "undefined" && process.env && key in process.env) {
      const value = process.env[key]
      if (typeof value === "string" && value.trim()) {
        return value
      }
    }
  }
  return undefined
}

export function getBackendBaseUrl() {
  const envValue =
    readEnvValue("VITE_BACKEND_URL", "NEXT_PUBLIC_BACKEND_URL", "BACKEND_API_URL", "BACKEND_URL") ??
    DEFAULT_BACKEND_URL

  return removeTrailingSlash(envValue.trim())
}

export function buildBackendUrl(path, searchParams) {
  const base = getBackendBaseUrl()
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  const url = `${base}${normalizedPath}`

  if (!searchParams || (searchParams instanceof URLSearchParams && !searchParams.toString())) {
    return url
  }

  let query = ""
  if (typeof searchParams === "string") {
    query = searchParams.trim()
  } else if (searchParams instanceof URLSearchParams) {
    query = searchParams.toString()
  } else if (typeof searchParams === "object") {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(searchParams)) {
      if (value === undefined || value === null) continue
      params.append(key, String(value))
    }
    query = params.toString()
  }

  return query ? `${url}?${query}` : url
}
