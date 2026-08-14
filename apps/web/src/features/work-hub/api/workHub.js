import { buildBackendUrl, safeParseJson } from "@/lib/api"

const CONTEXT_PATH = "/api/v1/work-hub/context"

export async function fetchWorkHubContext() {
  const response = await fetch(buildBackendUrl(CONTEXT_PATH), {
    credentials: "include",
    cache: "no-store",
  })
  const payload = await safeParseJson(response)
  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.error === "string"
          ? payload.error
          : `Work Hub 정보를 불러오지 못했습니다. (${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = payload
    throw error
  }
  return payload
}
