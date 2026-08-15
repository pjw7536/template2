import { ASSISTANT_KNOWLEDGE_MODES } from "./profileKeys"

const CURRENT_SCOPE_APP_KEYS = new Set([
  "emails",
  "observer",
  "appstore",
  "line-dashboard",
])

export function getAssistantKnowledgeCapability(appKey) {
  const normalizedAppKey = typeof appKey === "string" ? appKey.trim().toLowerCase() : ""
  const supportsCurrentScope = CURRENT_SCOPE_APP_KEYS.has(normalizedAppKey)
  return {
    supportsCurrentScope,
    defaultMode: supportsCurrentScope
      ? ASSISTANT_KNOWLEDGE_MODES.currentApp
      : ASSISTANT_KNOWLEDGE_MODES.auto,
  }
}
