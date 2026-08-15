import { buildOpenWebUIContextKey, getAssistantAppContext } from "./appContext"
import {
  ASSISTANT_KNOWLEDGE_MODES,
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
    appContextKey: buildOpenWebUIContextKey("assistant"),
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
  return true
}

export function resolveAssistantSurface({
  appKey,
  knowledgeMode = ASSISTANT_KNOWLEDGE_MODES.currentApp,
  pageContext = null,
  permissionGroups = [],
  ragIndexNames = [],
} = {}) {
  const appContext = getAssistantAppContext(appKey)
  if (!appContext) return null
  if (knowledgeMode === ASSISTANT_KNOWLEDGE_MODES.auto) {
    const observerInput = isAssistantAppContextReady({ appKey, pageContext })
      && appContext.key === "observer"
      ? {
          eqpId: pageContext.scope?.eqpId,
          from: pageContext.scope?.from,
          to: pageContext.scope?.to,
          logTypes: copyStringList(pageContext.scope?.logTypes),
          tipGroups: copyStringList(pageContext.scope?.tipGroups),
        }
      : {}
    const lineInput = isAssistantAppContextReady({ appKey, pageContext })
      && appContext.key === "line-dashboard"
      ? {
          view: pageContext.scope?.view === "history" ? "history" : "status",
          lineId: pageContext.scope?.lineId,
          ...(pageContext.scope?.from ? { from: pageContext.scope.from } : {}),
          ...(pageContext.scope?.to ? { to: pageContext.scope.to } : {}),
        }
      : {}
    const appstoreInput = appContext.key === "appstore" && pageContext?.kind === "appstore"
      ? {
          query: typeof pageContext.scope?.query === "string" ? pageContext.scope.query : "",
          category: typeof pageContext.scope?.category === "string"
            ? pageContext.scope.category
            : "all",
          selectedAppId: pageContext.scope?.selectedAppId ?? null,
        }
      : { query: "", category: "all", selectedAppId: null }
    return buildProfileSurface({
      mode: "auto",
      profileKey: ASSISTANT_PROFILE_KEYS.autoKnowledge,
      appContextKey: buildOpenWebUIContextKey(appContext.key),
      toolInputs: {
        "rag.search": {
          permissionGroups: copyStringList(permissionGroups),
          ragIndexes: copyStringList(ragIndexNames),
        },
        "observer.analysis": observerInput,
        "appstore.catalog": appstoreInput,
        "line-dashboard.snapshot": lineInput,
      },
    })
  }
  if (appContext.key === "portal") return buildGeneralAssistantSurface()

  if (appContext.key === "emails") {
    return buildProfileSurface({
      mode: "email",
      profileKey: ASSISTANT_PROFILE_KEYS.emails,
      appContextKey: "assistant",
      toolInputs: {
        "rag.search": {
          permissionGroups: copyStringList(permissionGroups),
          ragIndexes: copyStringList(ragIndexNames),
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
