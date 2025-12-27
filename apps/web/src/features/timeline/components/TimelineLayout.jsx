import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { HomeLayout } from "@/components/layout"
import {
  HomeNavbar,
  navigationItems as homeNavigationItems,
} from "@/features/home"
import { ChatWidget } from "@/features/assistant"

export default function TimelineLayout() {
  return (
    <RequireAuth>
      <>
        <HomeLayout
          header={<HomeNavbar navigationItems={homeNavigationItems} />}
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
