import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import {
  HomeNavbar,
  navigationItems as homeNavigationItems,
} from "@/features/home"
import { ChatWidget } from "@/features/assistant"

export default function TimelineLayout() {
  return (
    <RequireAuth>
      <div className="min-h-screen bg-background text-foreground">
        <HomeNavbar navigationItems={homeNavigationItems} />
        <main className="mx-auto w-full max-w-full px-4 py-1 sm:px-6">
          <Outlet />
        </main>
        <ChatWidget />
      </div>
    </RequireAuth>
  )
}
