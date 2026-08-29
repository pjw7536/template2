// 파일 경로: src/features/line-dashboard/api/getAirflowDagOverview.js
import { buildBackendUrl } from "@/lib/api"

const DEFAULT_PUBLIC_BASE_URL = "/airflow"
const REQUEST_TIMEOUT_MS = 15_000

export async function getAirflowDagOverview() {
  const endpoint = buildBackendUrl("/api/v1/line-dashboard/airflow/dag-overview")
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(endpoint, {
      credentials: "include",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      const backendMessage = [payload?.error, payload?.message].find(
        (value) => typeof value === "string",
      )
      const message =
        backendMessage ??
        `Airflow API 요청이 실패했습니다 (${response.status} ${response.statusText})`
      throw new Error(message)
    }
    return payload
  } catch (error) {
    const message =
      error?.name === "AbortError"
        ? "Airflow DAG 정보 요청 시간이 초과되었습니다."
        : error?.message ?? "Airflow DAG 정보를 불러오지 못했습니다."
    return {
      baseUrl: DEFAULT_PUBLIC_BASE_URL,
      error: message,
    }
  } finally {
    clearTimeout(timeoutId)
  }
}
