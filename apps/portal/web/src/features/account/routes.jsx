import { lazy } from "react"
import { Navigate } from "react-router-dom"

import { lazyNamed } from "@/lib/react/lazyNamed"

const AccountSettingsShell = lazyNamed(
  () => import("./components/AccountSettingsShell"),
  "AccountSettingsShell",
)
const AccountPage = lazy(() => import("./pages/AccountPage"))
const MembersPage = lazy(() => import("./pages/MembersPage"))
const PermissionsPage = lazy(() => import("./pages/PermissionsPage"))
const SettingsPage = lazy(() => import("./pages/SettingsPage"))

export const accountRoutes = [
  {
    path: "settings",
    element: <AccountSettingsShell />,
    children: [
      {
        element: <SettingsPage />,
        children: [
          {
            index: true,
            element: <Navigate to="account" replace />,
          },
          {
            path: "account",
            element: <AccountPage />,
          },
          {
            path: "members",
            element: <MembersPage />,
          },
          {
            path: "permissions",
            element: <PermissionsPage />,
          },
        ],
      },
    ],
  },
]
