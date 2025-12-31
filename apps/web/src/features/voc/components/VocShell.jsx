import { Outlet } from "react-router-dom"

import { TeamSwitcher } from "@/components/common"
import { AppShellLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { RequireAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"
import { DepartmentProvider } from "@/lib/affiliation"

import { VocHeader } from "./VocHeader"

export function VocShell() {
  const navigation = buildNavigationConfig()

  return (
    <RequireAuth>
      <>
        <DepartmentProvider>
          <AppShellLayout
            navItems={navigation.navMain}
            header={<VocHeader />}
            sidebarHeader={<TeamSwitcher disabled />}
            scrollAreaClassName="overflow-hidden"
          >
            <Outlet />
          </AppShellLayout>
        </DepartmentProvider>
        <ChatWidget />
      </>
    </RequireAuth>
  )
}
