// Standalone Appstore layout without the ESOP sidebar; only a slim header and centered content area.
import { Link, Outlet } from "react-router-dom"
import { Store } from "lucide-react"

import { ThemeToggle } from "@/components/common"
import { Button } from "@/components/ui/button"
import { RequireAuth } from "@/lib/auth"

export function AppstoreLayout() {
  return (
    <RequireAuth>
      <div className="min-h-screen bg-gradient-to-b from-muted/40 via-background to-background">
        <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3">
            <Link to="/appstore" className="flex items-center gap-2 font-semibold">
              <Store className="size-5 text-primary" aria-hidden />
              <span className="text-sm sm:text-base">Appstore</span>
            </Link>
            <div className="flex items-center gap-2">
              <Button asChild variant="ghost" size="sm">
                <Link to="/">Landing</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/ESOP_Dashboard">E-SOP Dashboard</Link>
              </Button>
              <ThemeToggle />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl px-4 py-8">
          <Outlet />
        </main>
      </div>
    </RequireAuth>
  )
}
