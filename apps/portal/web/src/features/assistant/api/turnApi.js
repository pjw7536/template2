import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { readAssistantSse } from "./standardSse"

const ASSISTANT_TURN_STREAM_PATH = "/api/v1/assistant/turns/stream"

export async function streamAssistantTurn(payload, { signal, onEvent } = {}) {
  const response = await fetch(buildBackendUrl(ASSISTANT_TURN_STREAM_PATH), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    credentials: "include",
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) {
    const errorPayload = await safeParseJson(response)
    const error = new Error(
      errorPayload.message || errorPayload.error || `Assistant Turn 요청에 실패했습니다. (${response.status})`,
    )
    error.status = response.status
    error.payload = errorPayload
    throw error
  }
  return readAssistantSse(response, { onEvent })
}
