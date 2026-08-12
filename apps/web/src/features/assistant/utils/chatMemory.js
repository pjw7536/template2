const DEFAULT_CONTEXT_KEY = "assistant"
const OPENWEBUI_CONTEXT_KEY = "assistant:openwebui"
const SHARED_MEMORY_KEY = "chatwidget:shared"
const OBSERVER_CONTEXT_PREFIX = "observer:"

function normalizeContextKey(contextKey) {
  return typeof contextKey === "string" && contextKey.trim()
    ? contextKey.trim()
    : DEFAULT_CONTEXT_KEY
}
export function getChatMemoryKey(contextKey) {
  const normalized = normalizeContextKey(contextKey)
  if (
    normalized === SHARED_MEMORY_KEY ||
    normalized === OPENWEBUI_CONTEXT_KEY ||
    normalized.startsWith(OBSERVER_CONTEXT_PREFIX)
  ) {
    return SHARED_MEMORY_KEY
  }
  return normalized
}

export function isSameChatMemory(firstContextKey, secondContextKey) {
  return getChatMemoryKey(firstContextKey) === getChatMemoryKey(secondContextKey)
}

export function formatChatHistoryContent(content, contextKey, requestContextKey) {
  if (normalizeContextKey(contextKey) === normalizeContextKey(requestContextKey)) {
    return content
  }

  const normalized = normalizeContextKey(contextKey)
  if (normalized === OPENWEBUI_CONTEXT_KEY) {
    return `[이전 대화 출처: 일반 Chat]\n${content}`
  }
  if (normalized.startsWith(OBSERVER_CONTEXT_PREFIX)) {
    const scopeLabel = normalizeContextKey(requestContextKey).startsWith(
      OBSERVER_CONTEXT_PREFIX,
    )
      ? " · 이전 조회 조건"
      : ""
    return `[이전 대화 출처: Observer${scopeLabel}]\n${content}`
  }
  return content
}
