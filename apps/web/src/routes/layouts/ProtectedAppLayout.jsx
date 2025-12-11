// src/routes/layouts/ProtectedAppLayout.jsx
import { Outlet, useLocation } from "react-router-dom"

import { RequireAuth } from "@/lib/auth"
import { AppLayout } from "@/components/layout"
import { HomeNavbar, navigationItems as homeNavigationItems } from "@/features/home"
import { LineDashboardLayout } from "@/features/line-dashboard"
import { ChatWidget } from "@/features/assistant"

const LINE_DASHBOARD_PREFIX = "/esop_dashboard"
const VOC_ROUTE_PATTERN = /\/voc(\/|$)|\/qna(\/|$)/
const INTERNAL_SCROLL_PREFIXES = ["/mailbox", "/emails"]
const LAYOUT_VARIANTS = {
  DEFAULT: "default",
  LINE_DASHBOARD: "line-dashboard",
}

function normalizePathname(pathname) {
  return typeof pathname === "string" ? pathname : ""
}

function getLayoutConfig(pathname) {
  const normalizedPath = normalizePathname(pathname).toLowerCase()
  const isLineDashboardRoute = normalizedPath.startsWith(LINE_DASHBOARD_PREFIX)
  const isVocRoute = VOC_ROUTE_PATTERN.test(normalizedPath)
  const isInternalScrollRoute = INTERNAL_SCROLL_PREFIXES.some((prefix) =>
    normalizedPath.startsWith(prefix),
  )

  return {
    variant: isLineDashboardRoute ? LAYOUT_VARIANTS.LINE_DASHBOARD : LAYOUT_VARIANTS.DEFAULT,
    contentMaxWidthClass: isVocRoute ? "max-w-screen-2xl" : undefined,
    scrollAreaClassName: isVocRoute || isInternalScrollRoute ? "overflow-hidden" : undefined,
  }
}

export function ProtectedAppLayout() {
  const location = useLocation()
  const { variant, contentMaxWidthClass, scrollAreaClassName } = getLayoutConfig(location?.pathname)
  const isLineDashboardRoute = variant === LAYOUT_VARIANTS.LINE_DASHBOARD

  const layout = isLineDashboardRoute ? (
    <LineDashboardLayout
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
    >
      <Outlet />
    </LineDashboardLayout>
  ) : (
    <AppLayout
      contentMaxWidthClass={contentMaxWidthClass}
      scrollAreaClassName={scrollAreaClassName}
      header={<HomeNavbar navigationItems={homeNavigationItems} />}
    >
      <Outlet />
    </AppLayout>
  )

  return (
    <RequireAuth>
      {layout}
      <ChatWidget />
    </RequireAuth>
  )
}
