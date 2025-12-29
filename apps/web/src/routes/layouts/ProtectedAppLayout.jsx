// 파일 경로: src/routes/layouts/ProtectedAppLayout.jsx
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppShellLayout, HomeLayout } from "@/components/layout"
import { TeamSwitcher } from "@/components/common"
import { buildNavigationConfig } from "@/lib/config/navigation-config"
import { DepartmentProvider } from "@/lib/affiliation"
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"
import { LineDashboardLayout } from "@/features/line-dashboard"
import { ChatWidget } from "@/features/assistant"
import { EmailsLayout } from "@/features/emails"
import { SettingsHeader } from "@/features/account"
import { VocHeader } from "@/features/voc"
import { getProtectedLayoutConfig, LAYOUT_VARIANTS } from "./protectedLayoutRules"

export function ProtectedAppLayout() {
  const location = useLocation()
  const { variant, contentMaxWidthClass, scrollAreaClassName } = getProtectedLayoutConfig(
    location?.pathname,
  )
  const navigation = buildNavigationConfig()

  let layout = null

  if (variant === LAYOUT_VARIANTS.LINE_DASHBOARD) {
    layout = (
      <LineDashboardLayout
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        <Outlet />
      </LineDashboardLayout>
    )
  } else if (variant === LAYOUT_VARIANTS.EMAILS) {
    layout = (
      <EmailsLayout
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        <Outlet />
      </EmailsLayout>
    )
  } else if (variant === LAYOUT_VARIANTS.MODELS) {
    layout = (
      <LineDashboardLayout
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        <Outlet />
      </LineDashboardLayout>
    )
  } else if (variant === LAYOUT_VARIANTS.SETTINGS) {
    layout = (
      <AppShellLayout
        navItems={navigation.navMain}
        header={<SettingsHeader />}
        sidebarHeader={<TeamSwitcher disabled />}
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
      >
        <Outlet />
      </AppShellLayout>
    )
  } else if (variant === LAYOUT_VARIANTS.VOC) {
    layout = (
      <DepartmentProvider>
        <AppShellLayout
          navItems={navigation.navMain}
          header={<VocHeader />}
          sidebarHeader={<TeamSwitcher disabled />}
          contentMaxWidthClass={contentMaxWidthClass}
          scrollAreaClassName={scrollAreaClassName}
        >
          <Outlet />
        </AppShellLayout>
      </DepartmentProvider>
    )
  } else {
    layout = (
      <HomeLayout
        contentMaxWidthClass={contentMaxWidthClass}
        scrollAreaClassName={scrollAreaClassName}
        header={<HomeNavbar navigationItems={homeNavigationItems} />}
      >
        <Outlet />
      </HomeLayout>
    )
  }

  return (
    <RequireAuth>
      {layout}
      <ChatWidget />
    </RequireAuth>
  )
}
