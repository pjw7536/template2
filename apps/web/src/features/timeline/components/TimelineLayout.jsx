import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import {
  LandingNavbar,
  navigationItems as landingNavigationItems,
} from "@/features/landing"

export default function TimelineLayout() {
  return (
    <RequireAuth>
      <div className="min-h-screen bg-background text-foreground">
        <LandingNavbar navigationItems={landingNavigationItems} />
        <main className="mx-auto w-full max-w-full px-4 py-1 sm:px-6">
          <Outlet />
        </main>
      </div>
    </RequireAuth>
  )
}
