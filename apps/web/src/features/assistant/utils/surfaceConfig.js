import { buildOpenWebUIContextKey, getAssistantAppContext } from "./appContext"
import {
  ASSISTANT_PROFILE_KEYS,
  ASSISTANT_PROFILE_VERSIONS,
} from "./profileKeys"

function copyStringList(values) {
  if (!Array.isArray(values)) return []
  return Array.from(
    new Set(
      values
        .map((value) => (typeof value === "string" ? value.trim() : ""))
        .filter(Boolean),
    ),
  )
}

function buildProfileSurface({ mode, profileKey, appContextKey, toolInputs }) {
  return {
    mode,
    profileKey,
    profileVersion: ASSISTANT_PROFILE_VERSIONS[profileKey],
    appContextKey,
    toolInputs,
  }
}

function buildGeneralAssistantSurface() {
  return buildProfileSurface({
    mode: "portal",
    profileKey: ASSISTANT_PROFILE_KEYS.portal,
    appContextKey: buildOpenWebUIContextKey("portal"),
    toolInputs: {},
  })
}

export function isAssistantAppContextReady({ appKey, pageContext = null } = {}) {
  const appContext = getAssistantAppContext(appKey)
  if (!appContext) return false
  if (appContext.key === "observer") {
    return Boolean(
      pageContext?.kind === "observer"
      && typeof pageContext.key === "string"
      && pageContext.key.startsWith("observer:v1:"),
    )
  }
  if (appContext.key === "appstore") {
    return pageContext?.kind === "appstore" && pageContext.key === "appstore:v1"
  }
  if (appContext.key === "line-dashboard") {
    return (
      pageContext?.kind === "line-dashboard"
      && pageContext.key === "line-dashboard:v1"
      && Boolean(pageContext.scope?.lineId)
    )
  }
  if (appContext.key === "emails") {
    const mailbox = String(pageContext?.scope?.mailbox || "").trim()
    return Boolean(
      pageContext?.kind === "emails"
      && mailbox
      && (mailbox.toLowerCase() !== "sent" || pageContext.scope?.emailId),
    )
  }
  return true
}

export function resolveAssistantSurface({
  appKey,
  useAppContext = true,
  pageContext = null,
  permissionGroups = [],
  ragIndexNames = [],
} = {}) {
  const appContext = getAssistantAppContext(appKey)
  if (!appContext) return null
  if (!useAppContext) return buildGeneralAssistantSurface()

  if (appContext.key === "emails") {
    if (!isAssistantAppContextReady({ appKey, pageContext })) return null
    return buildProfileSurface({
      mode: "email",
      profileKey: ASSISTANT_PROFILE_KEYS.emails,
      appContextKey: "assistant",
      toolInputs: {
        "rag.search": {
          permissionGroups: copyStringList(permissionGroups),
          ragIndexes: copyStringList(ragIndexNames),
          mailbox: String(pageContext.scope.mailbox).trim(),
          ...(pageContext.scope.emailId
            ? { emailId: String(pageContext.scope.emailId).trim() }
            : {}),
        },
      },
    })
  }

  if (appContext.key === "observer") {
    if (!isAssistantAppContextReady({ appKey, pageContext })) {
      return null
    }
    const scope = pageContext.scope && typeof pageContext.scope === "object"
      ? pageContext.scope
      : {}
    return buildProfileSurface({
      mode: "observer",
      profileKey: ASSISTANT_PROFILE_KEYS.observer,
      appContextKey: pageContext.key,
      toolInputs: {
        "observer.analysis": {
          eqpId: scope.eqpId,
          from: scope.from,
          to: scope.to,
          logTypes: copyStringList(scope.logTypes),
          tipGroups: copyStringList(scope.tipGroups),
        },
      },
    })
  }

  if (appContext.key === "appstore") {
    if (!isAssistantAppContextReady({ appKey, pageContext })) return null
    const scope = pageContext.scope && typeof pageContext.scope === "object"
      ? pageContext.scope
      : {}
    return buildProfileSurface({
      mode: "appstore",
      profileKey: ASSISTANT_PROFILE_KEYS.appstore,
      appContextKey: "appstore:v1",
      toolInputs: {
        "appstore.catalog": {
          query: typeof scope.query === "string" ? scope.query : "",
          category: typeof scope.category === "string" ? scope.category : "all",
          selectedAppId: scope.selectedAppId ?? null,
        },
      },
    })
  }

  if (appContext.key === "line-dashboard") {
    if (!isAssistantAppContextReady({ appKey, pageContext })) return null
    const scope = pageContext.scope && typeof pageContext.scope === "object"
      ? pageContext.scope
      : {}
    return buildProfileSurface({
      mode: "line-dashboard",
      profileKey: ASSISTANT_PROFILE_KEYS.lineDashboard,
      appContextKey: "line-dashboard:v1",
      toolInputs: {
        "line-dashboard.snapshot": {
          view: scope.view === "history" ? "history" : "status",
          lineId: scope.lineId,
          ...(scope.from ? { from: scope.from } : {}),
          ...(scope.to ? { to: scope.to } : {}),
        },
      },
    })
  }

  return buildProfileSurface({
    mode: "portal",
    profileKey: ASSISTANT_PROFILE_KEYS.portal,
    appContextKey: buildOpenWebUIContextKey(appContext.key),
    toolInputs: {},
  })
}
