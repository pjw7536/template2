// src/features/line-dashboard/api/get-line-ids.js
import { buildBackendUrl } from "@/lib/api"

/* ============================================================================
 * ✅ getDistinctLineIds()
 * - line_sdwt 테이블에서 중복 없는(line_id) 목록을 가져오는 함수입니다.
 * - NULL 값이나 빈 문자열('')은 제외합니다.
 * - 문자열이 아닌 타입(숫자, null 등)이 섞여 있을 가능성도 대비합니다.
 * ========================================================================== */
export async function getDistinctLineIds() {
  const endpoint = buildBackendUrl("/api/v1/line-dashboard/line-ids")

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5_000)

  let response

  try {
    response = await fetch(endpoint, { credentials: "include", signal: controller.signal })
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Timed out while loading line ids")
    }

    throw error
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const message = typeof payload?.error === "string" ? payload.error : `Failed to load line ids (${response.status})`
    throw new Error(message)
  }

  const payload = await response.json().catch(() => ({}))
  const rawLineIds = Array.isArray(payload?.lineIds) ? payload.lineIds : []

  return rawLineIds
    .filter((lineId) => typeof lineId === "string" && lineId.trim().length > 0)
    .map((lineId) => lineId.trim())
}
