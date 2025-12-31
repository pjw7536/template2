import { buildBackendUrl, getBackendBaseUrl } from "@/lib/api"

import { normalizeChatSources } from "../utils/normalizeChatSources"

const DEFAULT_CHAT_PATH = "/api/v1/assistant/chat"
const REQUEST_TIMEOUT_MS = 15000

function removeTrailingSlash(value) {
  return value.replace(/\/+$/, "")
}

function readEnvValue(keys) {
  for (const key of keys) {
    if (!key) continue
    try {
      const value =
        (typeof import.meta !== "undefined" && import.meta.env?.[key]) ||
        (typeof process !== "undefined" && process.env?.[key])

      if (typeof value === "string" && value.trim()) {
        return value.trim()
      }
    } catch {
      // ignore
    }
  }

  return undefined
}

function resolveChatEndpoint() {
  const envEndpoint = readEnvValue(["VITE_ASSISTANT_API_URL", "VITE_LLM_API_URL"])

  if (typeof envEndpoint === "string" && envEndpoint.trim()) {
    if (envEndpoint.startsWith("http")) {
      return removeTrailingSlash(envEndpoint)
    }

    return buildBackendUrl(envEndpoint)
  }

  return `${getBackendBaseUrl()}${DEFAULT_CHAT_PATH}`
}

function normalizeHistory(history) {
  if (!Array.isArray(history)) return []

  return history
    .map((message) => {
      if (!message) return null
      const role = typeof message.role === "string" ? message.role : undefined
      const content =
        typeof message.content === "string" && message.content.trim()
          ? message.content.trim()
          : undefined

      if (!role || !content) return null
      return { role, content }
    })
    .filter(Boolean)
}

function extractAssistantReply(payload) {
  if (!payload || typeof payload !== "object") return ""

  const candidates = []

  if (typeof payload.reply === "string") candidates.push(payload.reply)
  if (typeof payload.response === "string") candidates.push(payload.response)
  if (typeof payload.message === "string") candidates.push(payload.message)
  if (typeof payload.answer === "string") candidates.push(payload.answer)

  const choices = Array.isArray(payload.choices) ? payload.choices : []
  const choiceContent = choices
    .map((choice) => choice?.message?.content || choice?.text)
    .find((value) => typeof value === "string" && value.trim())
  if (choiceContent) {
    candidates.push(choiceContent)
  }

  const assistantMessage =
    candidates.find((value) => typeof value === "string" && value.trim()) ?? ""

  return assistantMessage.trim()
}

function extractAssistantSegments(payload) {
  if (!payload || typeof payload !== "object") return []

  const rawSegments = Array.isArray(payload.segments) ? payload.segments : []

  return rawSegments
    .map((segment) => {
      if (!segment || typeof segment !== "object") return null
      const reply =
        (typeof segment.reply === "string" && segment.reply.trim()) ||
        (typeof segment.answer === "string" && segment.answer.trim()) ||
        (typeof segment.message === "string" && segment.message.trim())

      if (!reply) return null

      return {
        reply: reply.trim(),
        sources: normalizeChatSources(segment.sources),
      }
    })
    .filter(Boolean)
}

function normalizeStringList(values) {
  if (!Array.isArray(values)) return []
  return values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
}

export async function sendChatMessage({ prompt, history = [], roomId, permissionGroups, ragIndexNames }) {
  if (typeof prompt !== "string" || !prompt.trim()) {
    throw new Error("메시지를 입력해주세요.")
  }

  // 1) 실행 환경별로 최적화된 엔드포인트를 선택한다.(VITE_*, proxy, backend URL 순)
  // 2) 서버가 기대하는 최소 필드(prompt, history, roomId)를 정규화한다.
  // 3) 네트워크/타임아웃/응답 포맷 오류를 한국어 에러 메시지로 래핑한다.
  const endpoint = resolveChatEndpoint()
  const normalizedPermissionGroups = normalizeStringList(permissionGroups)
  const normalizedRagIndexNames = normalizeStringList(ragIndexNames)
  const ragIndexNameValue = normalizedRagIndexNames.join(",")
  const payload = {
    prompt: prompt.trim(),
    history: normalizeHistory(history),
    roomId,
    ...(normalizedPermissionGroups.length
      ? { permission_groups: normalizedPermissionGroups }
      : {}),
    ...(ragIndexNameValue ? { rag_index_name: ragIndexNameValue } : {}),
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  let response
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("응답 대기 시간이 초과되었어요. 다시 시도해주세요.")
    }

    throw new Error("어시스턴트에 연결하지 못했어요. 네트워크를 확인해주세요.")
  } finally {
    clearTimeout(timeoutId)
  }

  let data = {}
  if (!response.ok) {
    data = await response.json().catch(() => ({}))
    const message =
      typeof data?.error === "string"
        ? data.error
        : `어시스턴트 응답을 불러오지 못했어요. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = data
    throw error
  }

  data = await response.json().catch(() => ({}))
  const reply = extractAssistantReply(data)
  const sources = normalizeChatSources(data.sources)
  const segments = extractAssistantSegments(data)

  return {
    reply,
    sources,
    segments,
    raw: data,
  }
}
