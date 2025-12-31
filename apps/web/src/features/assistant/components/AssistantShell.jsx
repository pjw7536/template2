import { Outlet } from "react-router-dom"

import { HomeLayout } from "@/components/layout"
import { RequireAuth } from "@/lib/auth"
import { HomeNavbar, navigationItems } from "@/features/home"

export function AssistantShell() {
  return (
    <RequireAuth>
      <HomeLayout
        header={<HomeNavbar navigationItems={navigationItems} />}
        contentMaxWidthClass="max-w-7xl"
        scrollAreaClassName="overflow-hidden"
      >
        <Outlet />
      </HomeLayout>
    </RequireAuth>
  )
}
