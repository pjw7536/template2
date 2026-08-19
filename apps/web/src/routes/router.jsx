// 파일 경로: src/routes/router.jsx
import { createBrowserRouter, Outlet, useLocation } from "react-router-dom"

import { PortalGlobalShell } from "@/components/layout"
import { AppAccessGate, AuthAutoLoginGate, PortalAccessGate, useAuth } from "@/lib/auth"
import { hasScopeAccess } from "@/lib/access/scopeAccess"
import { PageAssistantContextProvider } from "@/lib/assistant/pageContext"
import {
  getPortalAppDefinition,
  shouldHideAssistantWidget,
} from "@/lib/config/portalAppCatalog"

import { accessStatsRoutes } from "@/features/access-stats"
import { appstoreRoutes } from "@/features/appstore"
import { authRoutes } from "@/features/auth"
import { RouteErrorPage, errorRoutes } from "@/features/errors"
import { homeRoutes } from "@/features/home"
import { l0SpiderRoutes } from "@/features/l0-spider"
import { l1SpiderRoutes } from "@/features/l1-spider"
import { lineDashboardRoutes } from "@/features/line-dashboard"
import { l3SpiderRoutes } from "@/features/l3-spider"
import { pmSpiderRoutes } from "@/features/pm-spider"
import { spiderRoutes } from "@/features/spider"
import { teamstaffRoutes } from "@/features/teamstaff"
import { tttmSpiderRoutes } from "@/features/tttm-spider"
import { TkinPreventDashboardRoute, observerRoutes } from "@/features/observer"
import { vocRoutes } from "@/features/voc"
import { ChatWidget, assistantRoutes } from "@/features/assistant"
import { emailsRoutes, useEmailMailboxes } from "@/features/emails"
import { accountRoutes } from "@/features/account"

const esopDashboardRoutes = lineDashboardRoutes.map((route) => {
  if (route?.path !== "ESOP_Dashboard") return route

  return {
    ...route,
    children: [
      ...(Array.isArray(route.children) ? route.children : []),
      {
        path: "tip-status",
        caseSensitive: false,
        element: (
          <AppAccessGate scopeKey="observer" appName="Observer">
            <TkinPreventDashboardRoute />
          </AppAccessGate>
        ),
      },
      {
        path: "tip-status/:lineId",
        caseSensitive: false,
        element: (
          <AppAccessGate scopeKey="observer" appName="Observer">
            <TkinPreventDashboardRoute />
          </AppAccessGate>
        ),
      },
    ],
  }
})

function createAppRouteGroup(scopeKey, routes) {
  const appName = getPortalAppDefinition(scopeKey)?.routeAppName || scopeKey
  return {
    element: <AppAccessGate scopeKey={scopeKey} appName={appName}><Outlet /></AppAccessGate>,
    children: routes,
  }
}

const protectedFeatureRoutes = [
  ...spiderRoutes,
  createAppRouteGroup("l0-spider", l0SpiderRoutes),
  createAppRouteGroup("l1-spider", l1SpiderRoutes),
  createAppRouteGroup("teamstaff", teamstaffRoutes),
  createAppRouteGroup("line-dashboard", esopDashboardRoutes),
  createAppRouteGroup("l3-spider", l3SpiderRoutes),
  createAppRouteGroup("pm-spider", pmSpiderRoutes),
  createAppRouteGroup("tttm-spider", tttmSpiderRoutes),
  createAppRouteGroup("appstore", appstoreRoutes),
  createAppRouteGroup("access-stats", accessStatsRoutes),
  createAppRouteGroup("emails", emailsRoutes),
  createAppRouteGroup("voc", vocRoutes),
  createAppRouteGroup("observer", observerRoutes),
  ...accountRoutes,
]

function AssistantWidgetOutlet() {
  const { user } = useAuth()
  const location = useLocation()
  const hasPortalAccess = hasScopeAccess(user, "portal")
  const hasAssistantAccess = hasScopeAccess(user, "assistant")
  const hasEmailsAccess = hasScopeAccess(user, "emails")
  const { data: mailboxesData } = useEmailMailboxes({ enabled: hasPortalAccess && hasEmailsAccess })
  const availableMailboxes = Array.isArray(mailboxesData?.results)
    ? mailboxesData.results
    : []
  const hideChatWidget = shouldHideAssistantWidget(location.pathname)

  return (
    <PortalAccessGate allowUnapprovedPaths={["/settings", "/settings/account"]}>
      <PageAssistantContextProvider>
        <Outlet context={{ availableMailboxes }} />
        {hasPortalAccess && hasAssistantAccess && !hideChatWidget ? (
          <ChatWidget availableMailboxes={availableMailboxes} />
        ) : null}
      </PageAssistantContextProvider>
    </PortalAccessGate>
  )
}

function AssistantMailboxOutlet() {
  const { user } = useAuth()
  const hasPortalAccess = hasScopeAccess(user, "portal")
  const hasEmailsAccess = hasScopeAccess(user, "emails")
  const { data: mailboxesData } = useEmailMailboxes({ enabled: hasPortalAccess && hasEmailsAccess })
  const availableMailboxes = Array.isArray(mailboxesData?.results)
    ? mailboxesData.results
    : []

  return (
    <PortalAccessGate>
      <AppAccessGate scopeKey="assistant" appName="Assistant">
        <Outlet context={{ availableMailboxes }} />
      </AppAccessGate>
    </PortalAccessGate>
  )
}

const assistantWidgetRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <AssistantWidgetOutlet />,
      children: [
        ...homeRoutes,
        ...protectedFeatureRoutes,
      ],
    },
  ],
}

const assistantProtectedRoutes = {
  element: <AuthAutoLoginGate />,
  children: [
    {
      element: <AssistantMailboxOutlet />,
      children: assistantRoutes,
    },
  ],
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <PortalGlobalShell />,
    errorElement: (
      <PortalGlobalShell>
        <RouteErrorPage />
      </PortalGlobalShell>
    ),
    children: [
      ...authRoutes,
      assistantWidgetRoutes,
      assistantProtectedRoutes,
      ...errorRoutes,
    ],
  },
])
