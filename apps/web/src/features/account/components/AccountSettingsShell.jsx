import { Outlet, useLocation } from "react-router-dom"

import { AppShellLayout } from "@/components/layout"
import { RequireAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"

export function AccountSettingsShell() {
  const { pathname } = useLocation()
  const normalizedPath = pathname.replace(/\/+$/, "").toLowerCase()
  const isAccountPage = normalizedPath === "/settings/account"
  const isFixedHeightPage = normalizedPath === "/settings/account"
  const navigation = buildNavigationConfig({
    adminScopes: [],
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
