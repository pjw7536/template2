import LandingAppstorePage from "./pages/LandingAppstorePage"
import LandingEsopDashboardPage from "./pages/LandingEsopDashboardPage"
import LandingPage from "./pages/LandingPage"
import LandingQnaPage from "./pages/LandingQnaPage"
import { LandingLayout } from "./components/LandingLayout"

export const landingRoutes = [
  {
    element: <LandingLayout />,
    children: [
      {
        index: true,
        element: <LandingPage />,
      },
      {
        path: "landing",
        element: <LandingPage />,
      },
      {
        path: "landing/esop-dashboard",
        element: <LandingEsopDashboardPage />,
      },
      {
        path: "landing/appstore",
        element: <LandingAppstorePage />,
      },
      {
        path: "landing/qna",
        element: <LandingQnaPage />,
      },
    ],
  },
]
