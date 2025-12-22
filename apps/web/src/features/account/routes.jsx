import AccountPage from "./pages/AccountPage"
import MembersPage from "./pages/MembersPage"

export const accountRoutes = [
  {
    path: "account",
    element: <AccountPage />,
  },
  {
    path: "members",
    element: <MembersPage />,
  },
]
