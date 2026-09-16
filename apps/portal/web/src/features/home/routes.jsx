import { PortalHomeShell } from "@/components/layout"
import { lazy } from "react"

const HomePage = lazy(() => import("./pages/HomePage"))

export const homeRoutes = [
  {
    element: <PortalHomeShell />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
    ],
  },
]
