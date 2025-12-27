// src/routes/layouts/ProtectedAppLayout.jsx
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { HomeLayout } from "@/components/layout"
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"
import { LineDashboardLayout } from "@/features/line-dashboard"
import { ChatWidget } from "@/features/assistant"
import { EmailsLayout } from "@/features/emails"
import { getProtectedLayoutConfig, LAYOUT_VARIANTS } from "./protectedLayoutRules"

export function ProtectedAppLayout() {
  const location = useLocation()
  const { variant, contentMaxWidthClass, scrollAreaClassName } = getProtectedLayoutConfig(
    location?.pathname,
  )

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
