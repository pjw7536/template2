import { Outlet } from "react-router-dom"

import { HomeLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { HomeNavbar, navigationItems } from "@/features/home"
import { RequireAuth } from "@/lib/auth"

export function AppstoreShell() {
  return (
    <RequireAuth>
      <>
        <HomeLayout
          header={<HomeNavbar navigationItems={navigationItems} />}
          scrollAreaClassName="overflow-hidden"
        >
          <Outlet />
        </HomeLayout>
        <ChatWidget />
      </>
    </RequireAuth>
  )
}
