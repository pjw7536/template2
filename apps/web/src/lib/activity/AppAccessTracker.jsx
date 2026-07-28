import { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"

import { recordAppAccess } from "@/features/access-stats"
import { getScopeAccess } from "@/lib/access/scopeAccess"
import { useAuth } from "@/lib/auth"

import { getRequiredAppScopes, resolveAppAccessTarget } from "./appAccessCatalog"

export function AppAccessTracker() {
  const { user } = useAuth()
  const location = useLocation()
  const lastTrackedKeyRef = useRef("")

  useEffect(() => {
    if (!getScopeAccess(user, "portal")?.allowed) return

    const target = resolveAppAccessTarget(location.pathname)
    if (!target) return
    const requiredAppScopes = getRequiredAppScopes(target)
    if (
      target.requiresAppAccess !== false
      && requiredAppScopes.some((scopeKey) => !getScopeAccess(user, scopeKey)?.allowed)
    ) return

    const path = `${location.pathname}${location.search || ""}`
    const trackedKey = `${user.id || user.usr_id || "user"}:${path}`
    if (lastTrackedKeyRef.current === trackedKey) return
    lastTrackedKeyRef.current = trackedKey

    recordAppAccess({
      appId: target.appId,
      appName: target.appName,
      path,
    }).catch(() => {})
  }, [location.pathname, location.search, user])

  return null
}
