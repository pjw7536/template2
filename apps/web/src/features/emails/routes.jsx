import { EmailsShell } from "./components/EmailsShell"
import { EmailInboxPage } from "./pages/EmailInboxPage"
import { EmailMembersPage } from "./pages/EmailMembersPage"
import { EmailSentPage } from "./pages/EmailSentPage"

export const emailsRoutes = [
  {
    path: "emails",
    element: <EmailsShell />,
    children: [
      {
        path: "inbox",
        element: <EmailInboxPage />,
      },
      {
        path: "sent",
        element: <EmailSentPage />,
      },
      {
        path: "members",
        element: <EmailMembersPage />,
      },
    ],
  },
]
