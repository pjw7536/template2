import { buildBackendUrl } from "@/lib/api"

function normalizeText(value) {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value.trim() : String(value).trim()
}

function normalizePayload(payload) {
  const lines = (Array.isArray(payload?.lines) ? payload.lines : [])
    .map((line) => {
      const lineId = normalizeText(line?.lineId)
      const userSdwtProds = Array.from(
        new Set(
          (Array.isArray(line?.userSdwtProds) ? line.userSdwtProds : [])
            .map(normalizeText)
            .filter(Boolean),
        ),
      ).sort()
      return lineId && userSdwtProds.length ? { lineId, userSdwtProds } : null
    })
    .filter(Boolean)
  const userSdwtProds = Array.from(
    new Set(
      (Array.isArray(payload?.userSdwtProds) ? payload.userSdwtProds : [])
        .map(normalizeText)
        .filter(Boolean),
    ),
  ).sort()
  return { lines, userSdwtProds }
}

export async function getLineSdwtOptions() {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5_000)
  try {
    const response = await fetch(buildBackendUrl("/api/v1/account/line-sdwt-options"), {
      credentials: "include",
      signal: controller.signal,
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload?.error || `Failed to load line SDWT options (${response.status})`)
    }
    return normalizePayload(await response.json().catch(() => ({})))
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Timed out while loading line SDWT options")
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}
