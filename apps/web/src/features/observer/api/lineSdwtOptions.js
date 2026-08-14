import { buildBackendUrl } from "@/lib/api"

export async function getObserverLineSdwtOptions() {
  const response = await fetch(buildBackendUrl("/api/v1/line-dashboard/line-sdwt-options"), {
    credentials: "include",
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload?.error || `Failed to load line SDWT options (${response.status})`)
  }
  return response.json()
}
