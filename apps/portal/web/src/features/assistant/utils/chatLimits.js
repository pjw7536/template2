export const MAX_ASSISTANT_MESSAGE_CHARS = 10_000
export const MAX_ASSISTANT_SOURCES = 50
export const MAX_ASSISTANT_SOURCES_JSON_BYTES = 50 * 1024
export const MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES = 100 * 1024

const TRUNCATED_CONTENT_SUFFIX = "\n\n[저장 한도에 맞춰 답변 일부를 생략했습니다.]"

function jsonByteLength(value) {
  try {
    return new TextEncoder().encode(JSON.stringify(value)).length
  } catch {
    return Number.POSITIVE_INFINITY
  }
}

function reduceList(values) {
  if (!Array.isArray(values) || !values.length) return false
  if (values.length === 1) values.length = 0
  else values.splice(0, values.length, ...values.filter((_, index) => index % 2 === 0))
  return true
}

function normalizeAssistantContent(content) {
  const normalized = typeof content === "string" ? content.trim() : ""
  if (normalized.length <= MAX_ASSISTANT_MESSAGE_CHARS) return normalized
  const retainedLength = MAX_ASSISTANT_MESSAGE_CHARS - TRUNCATED_CONTENT_SUFFIX.length
  return `${normalized.slice(0, retainedLength).trimEnd()}${TRUNCATED_CONTENT_SUFFIX}`
}

function normalizeAssistantSources(sources) {
  const normalized = Array.isArray(sources) ? sources.slice(0, MAX_ASSISTANT_SOURCES) : []
  while (normalized.length && jsonByteLength(normalized) > MAX_ASSISTANT_SOURCES_JSON_BYTES) {
    normalized.pop()
  }
  return normalized
}

function normalizeContextSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) return null
  let normalized
  try {
    normalized = JSON.parse(JSON.stringify(snapshot))
  } catch {
    return null
  }
  while (jsonByteLength(normalized) > MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES) {
    const evidence = Array.isArray(normalized.evidence) ? normalized.evidence : []
    let reduced = false
    evidence.forEach((item) => {
      if (!item || typeof item !== "object") return
      reduced = reduceList(item.evidenceTargets) || reduced
      reduced = reduceList(item.evidenceIds) || reduced
    })
    if (!reduced) reduced = reduceList(evidence)
    if (!reduced) return null
  }
  return normalized
}

export function normalizeGeneratedAssistantMessage(message) {
  const normalized = {
    ...message,
    content: normalizeAssistantContent(message?.content),
    sources: normalizeAssistantSources(message?.sources),
  }
  const contextSnapshot = normalizeContextSnapshot(message?.contextSnapshot)
  if (contextSnapshot) normalized.contextSnapshot = contextSnapshot
  else delete normalized.contextSnapshot
  return normalized
}
