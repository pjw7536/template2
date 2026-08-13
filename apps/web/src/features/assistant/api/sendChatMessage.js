import { buildBackendUrl, getBackendBaseUrl } from "@/lib/api"

import { normalizeChatSources } from "../utils/normalizeChatSources"

const DEFAULT_CHAT_PATH = "/api/v1/assistant/chat"
const OPENWEBUI_STREAM_PATH = "/api/v1/assistant/openwebui-chat/stream"
const REQUEST_TIMEOUT_MS = 15000
const OPENWEBUI_REQUEST_TIMEOUT_MS = 130000

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
      // 실행 환경에서 env 접근을 지원하지 않으면 다음 후보를 확인합니다.
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

function buildChatPayload({
  prompt,
  history,
  roomId,
  permissionGroups,
  ragIndexNames,
  includeRagSettings,
  contextKey,
}) {
  const normalizedPermissionGroups = normalizeStringList(permissionGroups)
  const normalizedRagIndexNames = normalizeStringList(ragIndexNames)
  const ragIndexNameValue = normalizedRagIndexNames.join(",")
  return {
    prompt: prompt.trim(),
    history: normalizeHistory(history),
    roomId,
    ...(typeof contextKey === "string" && contextKey.trim()
      ? { contextKey: contextKey.trim() }
      : {}),
    ...(includeRagSettings && normalizedPermissionGroups.length
      ? { permission_groups: normalizedPermissionGroups }
      : {}),
    ...(includeRagSettings && ragIndexNameValue ? { rag_index_name: ragIndexNameValue } : {}),
  }
}

function createRequestController(externalSignal, timeoutMs) {
  const controller = new AbortController()
  let didTimeout = false
  const handleExternalAbort = () => controller.abort(externalSignal?.reason)
  if (externalSignal?.aborted) handleExternalAbort()
  else externalSignal?.addEventListener("abort", handleExternalAbort, { once: true })
  const timeoutId = setTimeout(() => {
    didTimeout = true
    controller.abort()
  }, timeoutMs)
  return {
    signal: controller.signal,
    didTimeout: () => didTimeout,
    cleanup: () => {
      clearTimeout(timeoutId)
      externalSignal?.removeEventListener("abort", handleExternalAbort)
    },
  }
}

function parseSseBlock(block) {
  const lines = block.split("\n")
  const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() || "message"
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
  if (!data) return { event, payload: {} }
  try {
    return { event, payload: JSON.parse(data) }
  } catch {
    throw new Error("스트리밍 응답 형식이 올바르지 않습니다.")
  }
}

async function readSseResponse(response, { onDelta, onMeta }) {
  const reader = response.body?.getReader?.()
  if (!reader) throw new Error("브라우저가 스트리밍 응답을 지원하지 않습니다.")

  const decoder = new TextDecoder()
  let buffer = ""
  let streamedReply = ""
  let finalReply = ""
  let meta = {}
  let didReceiveDone = false

  const handleBlock = (block) => {
    const { event, payload } = parseSseBlock(block)
    if (event === "meta") {
      meta = payload && typeof payload === "object" ? payload : {}
      onMeta?.(meta)
      return
    }
    if (event === "delta") {
      const content = typeof payload?.content === "string" ? payload.content : ""
      if (!content) return
      streamedReply += content
      onDelta?.(content)
      return
    }
    if (event === "done") {
      didReceiveDone = true
      finalReply = typeof payload?.reply === "string" ? payload.reply : streamedReply
      return
    }
    if (event === "error") {
      throw new Error(payload?.error || "OpenWebUI 스트리밍 응답에 실패했습니다.")
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      buffer = buffer.replace(/\r\n/g, "\n")
      let boundary = buffer.indexOf("\n\n")
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary).trim()
        buffer = buffer.slice(boundary + 2)
        if (block) handleBlock(block)
        boundary = buffer.indexOf("\n\n")
      }
      if (done) break
    }
    const trailingBlock = buffer.trim()
    if (trailingBlock) handleBlock(trailingBlock)
  } finally {
    reader.releaseLock?.()
  }

  if (!didReceiveDone) {
    throw new Error("OpenWebUI 응답이 완료되기 전에 연결이 종료되었습니다.")
  }
  const reply = (finalReply || streamedReply).trim()
  if (!reply) throw new Error("OpenWebUI 응답이 비어 있습니다.")
  return { reply, sources: [], segments: [], meta }
}

async function requestChatMessage({
  prompt,
  history = [],
  roomId,
  permissionGroups,
  ragIndexNames,
  endpoint,
  includeRagSettings,
  timeoutMs,
  signal,
  contextKey,
}) {
  if (typeof prompt !== "string" || !prompt.trim()) {
    throw new Error("메시지를 입력해주세요.")
  }

  // 1) 서버가 기대하는 최소 필드(prompt, history, roomId)를 정규화한다.
  // 2) 메일 RAG 요청일 때만 인덱스와 권한 그룹을 포함한다.
  // 3) 네트워크/타임아웃/응답 포맷 오류를 한국어 에러 메시지로 래핑한다.
  const payload = buildChatPayload({
    prompt,
    history,
    roomId,
    permissionGroups,
    ragIndexNames,
    includeRagSettings,
    contextKey,
  })

  const requestControl = createRequestController(signal, timeoutMs)

  let response
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(payload),
      signal: requestControl.signal,
    })
  } catch (error) {
    if (error?.name === "AbortError") {
      if (signal?.aborted && !requestControl.didTimeout()) {
        const cancelledError = new Error("응답 생성을 중지했습니다.")
        cancelledError.name = "AbortError"
        throw cancelledError
      }
      throw new Error("응답 대기 시간이 초과되었어요. 다시 시도해주세요.")
    }

    throw new Error("어시스턴트에 연결하지 못했어요. 네트워크를 확인해주세요.")
  } finally {
    requestControl.cleanup()
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

export function sendChatMessage(request) {
  return requestChatMessage({
    ...request,
    endpoint: resolveChatEndpoint(),
    includeRagSettings: true,
    timeoutMs: REQUEST_TIMEOUT_MS,
  })
}

export async function sendOpenWebUIStreamingMessage(request) {
  if (typeof request?.prompt !== "string" || !request.prompt.trim()) {
    throw new Error("메시지를 입력해주세요.")
  }

  const requestControl = createRequestController(
    request.signal,
    OPENWEBUI_REQUEST_TIMEOUT_MS,
  )
  try {
    const response = await fetch(buildBackendUrl(OPENWEBUI_STREAM_PATH), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      credentials: "include",
      body: JSON.stringify(
        buildChatPayload({
          ...request,
          includeRagSettings: false,
        }),
      ),
      signal: requestControl.signal,
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(
        typeof data?.error === "string"
          ? data.error
          : `어시스턴트 응답을 불러오지 못했어요. (status ${response.status})`,
      )
    }
    return await readSseResponse(response, request)
  } catch (error) {
    if (error?.name === "AbortError") {
      if (request.signal?.aborted && !requestControl.didTimeout()) {
        const cancelledError = new Error("응답 생성을 중지했습니다.")
        cancelledError.name = "AbortError"
        throw cancelledError
      }
      throw new Error("응답 대기 시간이 초과되었어요. 다시 시도해주세요.")
    }
    throw error
  } finally {
    requestControl.cleanup()
  }
}
