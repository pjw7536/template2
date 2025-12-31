import { Outlet } from "react-router-dom"

import { TeamSwitcher } from "@/components/common"
import { AppShellLayout } from "@/components/layout"
import { ChatWidget } from "@/features/assistant"
import { RequireAuth } from "@/lib/auth"
import { buildNavigationConfig } from "@/lib/config/navigationConfig"

import { SettingsHeader } from "./SettingsHeader"

export function AccountSettingsShell() {
  const navigation = buildNavigationConfig()

  return (
    <RequireAuth>
      <>
        <AppShellLayout
          navItems={navigation.navMain}
          header={<SettingsHeader />}
          sidebarHeader={<TeamSwitcher disabled />}
        >
          <Outlet />
        </AppShellLayout>
        <ChatWidget />
      </>
    </RequireAuth>
  )
}
