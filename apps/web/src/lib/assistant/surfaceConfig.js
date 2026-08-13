import { buildOpenWebUIContextKey, getAssistantAppContext } from "./appContext"
import { ASSISTANT_PROFILE_KEYS, ASSISTANT_PROFILE_VERSIONS } from "./profileKeys"

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

export function resolveAssistantSurface({
  appKey,
  pageContext = null,
  permissionGroups = [],
  ragIndexNames = [],
} = {}) {
  const appContext = getAssistantAppContext(appKey)
  if (!appContext) return null

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
    if (
      pageContext?.kind !== "observer"
      || typeof pageContext.key !== "string"
      || !pageContext.key.startsWith("observer:v1:")
    ) {
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

  return buildProfileSurface({
    mode: "portal",
    profileKey: ASSISTANT_PROFILE_KEYS.portal,
    appContextKey: buildOpenWebUIContextKey(appContext.key),
    toolInputs: {},
  })
}
