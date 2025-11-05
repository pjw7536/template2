// src/lib/api.js
const DEFAULT_BACKEND_URL = "http://localhost:8000/"

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

export function getBackendBaseUrl() {
  const envValue =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.BACKEND_API_URL ||
    process.env.BACKEND_URL

  const base = typeof envValue === "string" && envValue.trim().length > 0 ? envValue.trim() : DEFAULT_BACKEND_URL
  return removeTrailingSlash(base)
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
