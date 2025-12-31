import { Outlet } from "react-router-dom"

import { HomeLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { HomeNavbar, navigationItems } from "@/features/home"
import { RequireAuth } from "@/lib/auth"

export function TimelineShell() {
  return (
    <RequireAuth>
      <>
        <HomeLayout
          header={<HomeNavbar navigationItems={navigationItems} />}
          contentMaxWidthClass="max-w-full"
          scrollAreaClassName="overflow-hidden"
        >
          <Outlet />
        </HomeLayout>
        <ChatWidget />
      </>
    </RequireAuth>
  )
}
