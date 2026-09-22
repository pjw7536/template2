// src/lib/api.js
import { readEnvValue } from "@/lib/runtimeEnv"

const DEFAULT_BACKEND_URL = "http://localhost:8000/"

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

export function getBackendBaseUrl() {
  const envValue =
    readEnvValue("VITE_BACKEND_URL", "BACKEND_API_URL", "BACKEND_URL") ??
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

export async function safeParseJson(response) {
  try {
    return await response.json()
  } catch {
    return {}
  }
}
