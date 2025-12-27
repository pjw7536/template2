import { buildBackendUrl } from "@/lib/api"

function normalizeLineId(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizeUserSdwtProd(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizeLineRows(rawLines) {
  if (!Array.isArray(rawLines)) return []

  return rawLines
    .map((line) => {
      const lineId = normalizeLineId(line?.lineId)
      if (!lineId) return null

      const rawUserSdwtProds = Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : []
      const userSdwtProds = rawUserSdwtProds
        .map((value) => normalizeUserSdwtProd(value))
        .filter(Boolean)

      if (userSdwtProds.length === 0) return null

      return {
        lineId,
        userSdwtProds: Array.from(new Set(userSdwtProds)).sort(),
      }
    })
    .filter(Boolean)
}

function normalizeUserSdwtProds(rawUserSdwtProds) {
  if (!Array.isArray(rawUserSdwtProds)) return []
  const normalized = rawUserSdwtProds
    .map((value) => normalizeUserSdwtProd(value))
    .filter(Boolean)
  return Array.from(new Set(normalized)).sort()
}

export async function getLineSdwtOptions() {
  const endpoint = buildBackendUrl("/api/v1/account/line-sdwt-options")

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5_000)

  let response

  try {
    response = await fetch(endpoint, { credentials: "include", signal: controller.signal })
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Timed out while loading line SDWT options")
    }

    throw error
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const message =
      typeof payload?.error === "string"
        ? payload.error
        : `Failed to load line SDWT options (${response.status})`
    throw new Error(message)
  }

  const payload = await response.json().catch(() => ({}))

  return {
    lines: normalizeLineRows(payload?.lines),
    userSdwtProds: normalizeUserSdwtProds(payload?.userSdwtProds),
  }
}
