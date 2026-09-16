import { PORTAL_APP_CATALOG } from "../config/portalAppCatalog"

export const APP_ACCESS_RULES = PORTAL_APP_CATALOG

const APP_ACCESS_RULE_BY_ID = new Map(
  APP_ACCESS_RULES.map((rule) => [rule.appId, rule]),
)

export function getAppAccessDefinition(appId) {
  if (typeof appId !== "string") return null
  return APP_ACCESS_RULE_BY_ID.get(appId.trim().toLowerCase()) ?? null
}

function normalizePathname(pathname) {
  const normalizedPathname = typeof pathname === "string" && pathname ? pathname : "/"
  if (normalizedPathname === "/") return normalizedPathname
  return normalizedPathname.replace(/\/+$/, "").toLowerCase()
}

function matchesPathPrefix(pathname, prefix) {
  const normalizedPathname = pathname.toLowerCase()
  const normalizedPrefix = prefix.toLowerCase().replace(/\/+$/, "")
  if (!normalizedPrefix) return normalizedPathname === "/"
  return normalizedPathname === normalizedPrefix || normalizedPathname.startsWith(`${normalizedPrefix}/`)
}

export function resolveAppAccessTarget(pathname) {
  const normalizedPathname = normalizePathname(pathname)
  return APP_ACCESS_RULES.find((rule) => {
    if (rule.matches?.(normalizedPathname)) return true
    return rule.prefixes?.some((prefix) => matchesPathPrefix(normalizedPathname, prefix))
  }) ?? null
}

export function getRequiredAppScopes(target) {
  if (!target || target.requiresAppAccess === false) return []
  const scopes = target.requiredAppScopes || (target.appId ? [target.appId] : [])
  return scopes.filter(Boolean)
}
