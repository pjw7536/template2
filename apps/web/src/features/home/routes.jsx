import { PortalHomeShell } from "@/components/layout"
import { lazy } from "react"

const HomePage = lazy(() => import("./pages/HomePage"))
const ReactLogoBlankPage = lazy(() => import("./pages/ReactLogoBlankPage"))

export const homeRoutes = [
  {
    element: <PortalHomeShell />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: "react-logo-preview",
        element: <ReactLogoBlankPage />,
      },
    ],
  },
]
