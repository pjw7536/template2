// src/features/line-dashboard/api/get-airflow-dag-overview.js
const DEFAULT_INTERNAL_BASE_URL = "http://localhost/airflow"
const DEFAULT_PUBLIC_BASE_URL = "https://plane.samsungds.net/airflow"

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

function resolveBaseUrls() {
  const apiCandidate =
    readEnvValue(
      "AIRFLOW_INTERNAL_BASE_URL",
      "AIRFLOW_BASE_URL",
      "AIRFLOW_URL",
      "VITE_AIRFLOW_BASE_URL",
    ) ?? DEFAULT_INTERNAL_BASE_URL

  const publicCandidate =
    readEnvValue(
      "VITE_AIRFLOW_BASE_URL",
      "AIRFLOW_PUBLIC_BASE_URL",
    ) ?? apiCandidate ?? DEFAULT_PUBLIC_BASE_URL

  return {
    apiBaseUrl: sanitizeBaseUrl(apiCandidate, DEFAULT_INTERNAL_BASE_URL),
    displayBaseUrl: sanitizeBaseUrl(publicCandidate, DEFAULT_PUBLIC_BASE_URL),
  }
}

function resolveCredentials() {
  const username =
    readEnvValue("AIRFLOW_USERNAME", "VITE_AIRFLOW_USERNAME") ?? "airflow"
  const password =
    readEnvValue("AIRFLOW_PASSWORD", "VITE_AIRFLOW_PASSWORD") ?? "airflow"

  if (!username || !password) {
    return { username: "", password: "" }
  }

  return { username, password }
}

function sanitizeBaseUrl(rawUrl, fallback) {
  if (typeof rawUrl !== "string") {
    return fallback ?? DEFAULT_PUBLIC_BASE_URL
  }

  const trimmed = rawUrl.trim()
  if (!trimmed) return fallback ?? DEFAULT_PUBLIC_BASE_URL

  return trimmed.replace(/\/+$/, "")
}

function createAuthHeader(username, password) {
  if (!username || !password) return null
  const raw = `${username}:${password}`
  if (typeof window !== "undefined" && typeof window.btoa === "function") {
    return `Basic ${window.btoa(raw)}`
  }
  if (typeof Buffer !== "undefined") {
    return `Basic ${Buffer.from(raw, "utf8").toString("base64")}`
  }
  return null
}

async function safeJson(response) {
  try {
    return await response.json()
  } catch (_error) {
    return null
  }
}

function normalizeTags(rawTags) {
  if (!Array.isArray(rawTags)) return []
  return rawTags
    .map((tag) => {
      if (!tag) return null
      if (typeof tag === "string") return tag
      if (typeof tag === "object" && typeof tag.name === "string") return tag.name
      return null
    })
    .filter(Boolean)
}

function normalizeOwners(rawOwners) {
  if (!Array.isArray(rawOwners)) return []
  return rawOwners
    .map((owner) => (typeof owner === "string" ? owner : null))
    .filter(Boolean)
}

function getTimetableDescription(dag) {
  if (!dag || typeof dag !== "object") return ""
  if (dag.timetable_description) return dag.timetable_description
  if (dag.schedule_interval) {
    const interval = dag.schedule_interval
    if (typeof interval === "string") return interval
    if (typeof interval === "object") {
      const type = interval.__type ?? interval.type
      const value = interval.value ?? interval.days ?? interval.seconds
      if (type && value) return `${type} (${value})`
      if (value) return `${value}`
    }
  }
  return ""
}

async function fetchLatestDagRun(baseUrl, dagId, headers) {
  const url = `${baseUrl}/api/v1/dags/${encodeURIComponent(dagId)}/dagRuns?limit=1&order_by=-execution_date`

  try {
    const response = await fetch(url, {
      headers,
      cache: "no-store",
    })

    if (!response.ok) {
      return null
    }

    const payload = await safeJson(response)
    if (!payload || !Array.isArray(payload.dag_runs) || payload.dag_runs.length === 0) {
      return null
    }

    const latestRun = payload.dag_runs[0]
    return {
      runId: latestRun.dag_run_id ?? null,
      state: latestRun.state ?? null,
      executionDate: latestRun.execution_date ?? null,
      startDate: latestRun.start_date ?? null,
      endDate: latestRun.end_date ?? null,
    }
  } catch (_error) {
    return null
  }
}

function computeTotals(dags) {
  const total = dags.length
  const paused = dags.filter((dag) => dag.isPaused).length
  const active = dags.filter((dag) => dag.isActive && !dag.isPaused).length
  const failed = dags.filter((dag) => dag.latestRun?.state?.toLowerCase() === "failed").length

  return {
    total,
    active,
    paused,
    failed,
  }
}

export async function getAirflowDagOverview() {
  const { apiBaseUrl, displayBaseUrl } = resolveBaseUrls()
  const { username, password } = resolveCredentials()

  const headers = {
    Accept: "application/json",
  }

  const authHeader = createAuthHeader(username, password)
  if (authHeader) {
    headers.Authorization = authHeader
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/dags?limit=200`, {
      headers,
      cache: "no-store",
    })

    if (!response.ok) {
      const payload = await safeJson(response)
      const detail = payload?.detail ?? payload?.error ?? ""
      const suffix = detail ? `: ${detail}` : ""
      throw new Error(`Airflow API 요청이 실패했습니다 (${response.status} ${response.statusText})${suffix}`)
    }

    const payload = await safeJson(response)
    const rawDags = Array.isArray(payload?.dags) ? payload.dags : []

    const dagSummaries = await Promise.all(
      rawDags.map(async (dag) => {
        const dagId = dag.dag_id ?? ""
        const latestRun = dagId ? await fetchLatestDagRun(apiBaseUrl, dagId, headers) : null

        return {
          dagId,
          description: dag.description ?? "",
          isPaused: Boolean(dag.is_paused),
          isActive: dag.is_active !== undefined ? Boolean(dag.is_active) : !dag.is_paused,
          owners: normalizeOwners(dag.owners),
          tags: normalizeTags(dag.tags),
          timetable: getTimetableDescription(dag),
          nextRun: dag.next_dagrun ?? null,
          nextRunCreateAfter: dag.next_dagrun_create_after ?? null,
          latestRun,
        }
      })
    )

    const totals = computeTotals(dagSummaries)

    return {
      baseUrl: displayBaseUrl,
      fetchedAt: new Date().toISOString(),
      totals,
      dags: dagSummaries,
    }
  } catch (error) {
    return {
      baseUrl: displayBaseUrl,
      error: error?.message ?? "Airflow DAG 정보를 불러오지 못했습니다.",
    }
  }
}
