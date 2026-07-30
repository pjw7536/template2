// 파일 경로: src/features/tttm-spider/api/tttmSpiderApi.js
// TTTM Spider 백엔드 API 요청 유틸입니다. (fetch 래퍼, l3-spider 패턴 미러)
import { buildBackendUrl, safeParseJson } from "@/lib/api"

const BASE_PATH = "/api/v1/tttm_spider"

async function request(path, options = {}) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}${path}`), {
    credentials: "include",
    cache: "no-store",
    ...options,
  })
  const payload = await safeParseJson(response)
  if (!response.ok) {
    const message =
      typeof payload?.error === "string"
        ? payload.error
        : typeof payload?.detail === "string"
          ? payload.detail
          : `TTTM Spider 요청 실패 (${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return payload
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export function fetchTttmComboOptions({ source = "comp", level, line, eqp, chamber }) {
  const params = new URLSearchParams({ source, level })
  if (line) params.append("line", line)
  if (eqp) params.append("eqp", eqp)
  if (chamber) params.append("chamber", chamber)
  return request(`/combo/options?${params.toString()}`)
}

export function fetchTttmComboTypes() {
  return request("/combo/types")
}

export function fetchTttmComboDataTypes() {
  return request("/combo/data-types")
}

export function fetchTttmLotwf(eqp, chamber) {
  const params = new URLSearchParams({ eqp, chamber })
  return request(`/targets/lotwf?${params.toString()}`)
}

export function fetchTttmEqps() {
  return request("/targets/eqps")
}

export function fetchTttmChambers(eqp) {
  const params = new URLSearchParams({ eqp })
  return request(`/targets/chambers?${params.toString()}`)
}

export function fetchTttmGolden(recipe) {
  const params = new URLSearchParams()
  if (recipe) params.set("recipe", recipe)
  const q = params.toString()
  return request(`/targets/golden${q ? `?${q}` : ""}`)
}

export function fetchTttmDashboardData(payload) {
  return postJson("/dashboard/data", payload)
}

export function fetchTttmSensorTrace(payload) {
  return postJson("/sensor-trace", payload)
}

export function fetchTttmResultStatus(items) {
  return postJson("/targets/result-status", { items })
}
