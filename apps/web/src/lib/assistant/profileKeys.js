export const ASSISTANT_PROFILE_KEYS = Object.freeze({
  portal: "portal-default",
  emails: "email-rag",
  observer: "observer-analysis",
  appstore: "appstore-context",
  lineDashboard: "line-dashboard-context",
})

export const ASSISTANT_PROFILE_VERSIONS = Object.freeze({
  [ASSISTANT_PROFILE_KEYS.portal]: 2,
  [ASSISTANT_PROFILE_KEYS.emails]: 1,
  [ASSISTANT_PROFILE_KEYS.observer]: 1,
  [ASSISTANT_PROFILE_KEYS.appstore]: 1,
  [ASSISTANT_PROFILE_KEYS.lineDashboard]: 1,
})
