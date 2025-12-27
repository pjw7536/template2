import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { HomeLayout } from "@/components/layout"
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"

export function AssistantLayout() {
  return (
    <RequireAuth>
      <HomeLayout
        header={<HomeNavbar navigationItems={homeNavigationItems} />}
        contentMaxWidthClass="max-w-7xl"
        scrollAreaClassName="overflow-hidden"
      >
        <Outlet />
      </HomeLayout>
    </RequireAuth>
  )
}
