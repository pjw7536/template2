import { EmailInboxPage } from "./pages/EmailInboxPage"
import { EmailMembersPage } from "./pages/EmailMembersPage"
import { EmailSentPage } from "./pages/EmailSentPage"

export const emailsRoutes = [
  {
    path: "emails/inbox",
    element: <EmailInboxPage />,
  },
  {
    path: "emails/sent",
    element: <EmailSentPage />,
  },
  {
    path: "emails/members",
    element: <EmailMembersPage />,
  },
]
