import { EmailInboxPage } from "./pages/EmailInboxPage"
import { EmailMembersPage } from "./pages/EmailMembersPage"

export const emailsRoutes = [
  {
    path: "emails",
    element: <EmailInboxPage />,
  },
  {
    path: "emails/members",
    element: <EmailMembersPage />,
  },
]
