import { Navigate } from "react-router-dom"

import AccountPage from "./pages/AccountPage"
import MembersPage from "./pages/MembersPage"
import SettingsPage from "./pages/SettingsPage"

export const accountRoutes = [
  {
    path: "settings",
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
    ],
  },
]
