import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"

export function AssistantLayout() {
  return (
    <RequireAuth>
      <div className="min-h-screen bg-background text-foreground">
        <HomeNavbar navigationItems={homeNavigationItems} />
        <main className="mx-auto w-full max-w-7xl px-4 py-3 sm:px-6">
          <Outlet />
        </main>
      </div>
    </RequireAuth>
  )
}
