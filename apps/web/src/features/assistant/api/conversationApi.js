import { buildBackendUrl } from "@/lib/api"

const CONVERSATIONS_PATH = "/api/v1/assistant/conversations"

async function requestConversationApi(path, options = {}) {
  const response = await fetch(buildBackendUrl(path), {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  })
  if (response.status === 204) return {}
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(
      typeof payload?.error === "string"
        ? payload.error
        : `대화 정보를 처리하지 못했어요. (status ${response.status})`,
    )
    error.status = response.status
    error.payload = payload
    throw error
  }
  return payload
}

function conversationPath(conversationId, suffix = "") {
  const normalizedId = encodeURIComponent(String(conversationId || ""))
  return `${CONVERSATIONS_PATH}/${normalizedId}${suffix}`
}

function buildQuery(params = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return
    searchParams.set(key, String(value))
  })
  const query = searchParams.toString()
  return query ? `?${query}` : ""
}

export async function fetchAssistantConversationPage({
  search = "",
  cursor = "",
  limit = 20,
  archived = false,
  signal,
} = {}) {
  const payload = await requestConversationApi(
    `${CONVERSATIONS_PATH}${buildQuery({
      search,
      cursor,
      limit: limit === 20 ? "" : limit,
      archived: archived ? "true" : "",
    })}`,
    { signal },
  )
  return {
    results: Array.isArray(payload?.results) ? payload.results : [],
    nextCursor: typeof payload?.nextCursor === "string" ? payload.nextCursor : "",
    hasMore: payload?.hasMore === true,
  }
}

export function createAssistantConversation({ name } = {}) {
  return requestConversationApi(CONVERSATIONS_PATH, {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export function deleteAssistantConversation(conversationId) {
  return requestConversationApi(conversationPath(conversationId), {
    method: "DELETE",
  })
}

export function updateAssistantConversation(conversationId, updates) {
  return requestConversationApi(conversationPath(conversationId), {
    method: "PATCH",
    body: JSON.stringify(updates || {}),
  })
}

export function generateAssistantConversationTitle(conversationId) {
  return requestConversationApi(conversationPath(conversationId, "/generate-title"), {
    method: "POST",
  })
}

export async function fetchAssistantConversationMessagePage(
  conversationId,
  { before = "", limit = 20, signal } = {},
) {
  const payload = await requestConversationApi(
    conversationPath(
      conversationId,
      `/messages${buildQuery({ before, limit: limit === 20 ? "" : limit })}`,
    ),
    { signal },
  )
  return {
    results: Array.isArray(payload?.results) ? payload.results : [],
    nextCursor: typeof payload?.nextCursor === "string" ? payload.nextCursor : "",
    hasMore: payload?.hasMore === true,
  }
}

export function clearAssistantConversationMessages(conversationId) {
  return requestConversationApi(conversationPath(conversationId, "/messages"), {
    method: "DELETE",
  })
}

export function refreshAssistantConversationSummary(
  conversationId,
  contextKey,
) {
  if (typeof contextKey !== "string" || !contextKey.trim()) {
    throw new Error("Assistant summary contextKey가 필요합니다.")
  }
  return requestConversationApi(conversationPath(conversationId, "/refresh-summary"), {
    method: "POST",
    body: JSON.stringify({ contextKey: contextKey.trim() }),
  })
}

export function submitAssistantMessageFeedback(
  conversationId,
  messageId,
  { rating, reason = "" },
) {
  return requestConversationApi(
    conversationPath(
      conversationId,
      `/messages/${encodeURIComponent(String(messageId || ""))}/feedback`,
    ),
    {
      method: "PUT",
      body: JSON.stringify({ rating, reason }),
    },
  )
}

export function deleteAssistantMessageFeedback(conversationId, messageId) {
  return requestConversationApi(
    conversationPath(
      conversationId,
      `/messages/${encodeURIComponent(String(messageId || ""))}/feedback`,
    ),
    { method: "DELETE" },
  )
}

export async function exportAssistantConversation(conversationId, format = "markdown") {
  const response = await fetch(
    buildBackendUrl(
      conversationPath(conversationId, `/export${buildQuery({ exportFormat: format })}`),
    ),
    { credentials: "include" },
  )
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload?.error || "대화를 내보내지 못했어요.")
  }
  const blob = await response.blob()
  const extension = format === "csv" ? "csv" : "md"
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `assistant-${conversationId}.${extension}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
