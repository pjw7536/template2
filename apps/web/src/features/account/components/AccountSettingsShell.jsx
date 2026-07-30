import { Outlet, useLocation } from "react-router-dom"

import { AppShellLayout } from "@/components/layout"
import { RequireAuth, useAuth } from "@/lib/auth"
import { hasScopeRole } from "@/lib/access/scopeAccess"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"

export function AccountSettingsShell() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const normalizedPath = pathname.replace(/\/+$/, "").toLowerCase()
  const isAccountPage = normalizedPath === "/settings/account"
  const isFixedHeightPage = [
    "/settings/account",
    "/settings/members",
    "/settings/permissions",
  ].includes(normalizedPath)
  const navigation = buildNavigationConfig({
    adminScopes: hasScopeRole(user, "portal") ? ["portal"] : [],
  })

  return (
    <RequireAuth>
      <AppShellLayout
        navItems={navigation.navMain}
        scrollAreaClassName={
          isFixedHeightPage
            ? "h-full min-h-0 overflow-hidden"
            : "overflow-y-auto"
        }
        innerClassName={
          isAccountPage
            ? "mx-auto flex h-full min-h-0 w-full flex-col overflow-hidden"
            : undefined
        }
        insetClassName={isAccountPage ? "h-full min-h-0 overflow-hidden" : undefined}
        paddingClassName={isAccountPage ? "px-4" : undefined}
      >
        <Outlet />
      </AppShellLayout>
    </RequireAuth>
  )
}
