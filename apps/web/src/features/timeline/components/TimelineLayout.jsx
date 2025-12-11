import { Outlet } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppLayout } from "@/components/layout"
import {
  HomeNavbar,
  navigationItems as homeNavigationItems,
} from "@/features/home"
import { ChatWidget } from "@/features/assistant"

export default function TimelineLayout() {
  return (
    <RequireAuth>
      <>
        <AppLayout
          header={<HomeNavbar navigationItems={homeNavigationItems} />}
          contentMaxWidthClass="max-w-full"
          scrollAreaClassName="overflow-hidden"
        >
          <Outlet />
        </AppLayout>
        <ChatWidget />
      </>
    </RequireAuth>
  )
}
