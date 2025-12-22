// src/features/line-dashboard/api/line-jira-key.js
// 라인별 Jira project key 조회/저장 API 래퍼
import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { unwrapErrorMessage } from "../utils/line-settings"

function buildApiError(response, payload, fallbackMessage) {
  const apiMessage =
    payload && typeof payload === "object" && typeof payload.error === "string"
      ? payload.error
      : ""
  const message = unwrapErrorMessage(apiMessage) || fallbackMessage
  const error = new Error(message)
  error.status = response.status
  return error
}

export async function fetchLineJiraKey(lineId) {
  if (!lineId) {
    return { jiraKey: "" }
  }

  const endpoint = buildBackendUrl("/api/v1/account/affiliation/jira-key", { lineId })
  const response = await fetch(endpoint, {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load Jira key (status ${response.status})`,
    )
  }

  return { jiraKey: typeof payload?.jiraKey === "string" ? payload.jiraKey : "" }
}

export async function updateLineJiraKey({ lineId, jiraKey }) {
  const endpoint = buildBackendUrl("/api/v1/account/affiliation/jira-key")
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      lineId,
      jiraKey: typeof jiraKey === "string" ? jiraKey : "",
    }),
  })

  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to update Jira key (status ${response.status})`,
    )
  }

  return { jiraKey: typeof payload?.jiraKey === "string" ? payload.jiraKey : "" }
}
