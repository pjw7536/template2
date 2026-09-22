import { lazyNamed } from "@/lib/react/lazyNamed"

const EmailsShell = lazyNamed(() => import("./components/EmailsShell"), "EmailsShell")
const EmailInboxPage = lazyNamed(() => import("./pages/EmailInboxPage"), "EmailInboxPage")
const EmailMembersPage = lazyNamed(
  () => import("./pages/EmailMembersPage"),
  "EmailMembersPage",
)
const EmailSentPage = lazyNamed(() => import("./pages/EmailSentPage"), "EmailSentPage")

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
