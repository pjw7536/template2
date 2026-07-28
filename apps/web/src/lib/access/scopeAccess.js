export function getScopeAccess(user, scopeKey) {
  if (!scopeKey || !user?.scope_access || typeof user.scope_access !== "object") return null
  const access = user.scope_access[scopeKey]
  return access && typeof access === "object" ? access : null
}

export function hasScopeAccess(user, scopeKey) {
  return Boolean(getScopeAccess(user, scopeKey)?.allowed)
}

export function hasEveryScopeAccess(user, scopeKeys) {
  const keys = Array.isArray(scopeKeys) ? scopeKeys.filter(Boolean) : []
  return keys.every((scopeKey) => hasScopeAccess(user, scopeKey))
}

export function hasAnyScopeAccess(user, scopeKeys) {
  const keys = Array.isArray(scopeKeys) ? scopeKeys.filter(Boolean) : []
  return keys.some((scopeKey) => hasScopeAccess(user, scopeKey))
}

export function hasScopeRole(user, scopeKey, role = "admin") {
  const access = getScopeAccess(user, scopeKey)
  return Boolean(access?.allowed && access?.role === role)
}

export function isScopeAccessBypass(access) {
  return access?.source === "superuser_bypass"
}
