export const ASSISTANT_PROFILE_KEYS = Object.freeze({
  portal: "portal-default",
  emails: "email-rag",
  observer: "observer-analysis",
  appstore: "appstore-context",
  lineDashboard: "line-dashboard-context",
  autoKnowledge: "auto-knowledge",
})

export const ASSISTANT_PROFILE_VERSIONS = Object.freeze({
  [ASSISTANT_PROFILE_KEYS.portal]: 2,
  [ASSISTANT_PROFILE_KEYS.emails]: 2,
  [ASSISTANT_PROFILE_KEYS.observer]: 2,
  [ASSISTANT_PROFILE_KEYS.appstore]: 2,
  [ASSISTANT_PROFILE_KEYS.lineDashboard]: 2,
  [ASSISTANT_PROFILE_KEYS.autoKnowledge]: 1,
})

export const ASSISTANT_KNOWLEDGE_MODES = Object.freeze({
  currentApp: "current_app",
  auto: "auto",
})
