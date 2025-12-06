import { Navigate } from "react-router-dom"

import HomeAppstorePage from "./pages/HomeAppstorePage"
import HomeEsopDashboardPage from "./pages/HomeEsopDashboardPage"
import HomePage from "./pages/HomePage"
import HomeVocPage from "./pages/HomeVocPage"
import { HomeLayout } from "./components/HomeLayout"

export const homeRoutes = [
  {
    element: <HomeLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: "home",
        element: <HomePage />,
      },
      {
        path: "home/esop-dashboard",
        element: <HomeEsopDashboardPage />,
      },
      {
        path: "appstore",
        element: <HomeAppstorePage />,
      },
      {
        path: "home/appstore",
        element: <Navigate to="/appstore" replace />,
      },
      {
        path: "home/voc",
        element: <HomeVocPage />,
      },
      // Legacy redirects for previous landing routes
      {
        path: "landing",
        element: <Navigate to="/home" replace />,
      },
      {
        path: "landing/esop-dashboard",
        element: <Navigate to="/home/esop-dashboard" replace />,
      },
      {
        path: "landing/appstore",
        element: <Navigate to="/appstore" replace />,
      },
      {
        path: "home/qna",
        element: <Navigate to="/home/voc" replace />,
      },
      {
        path: "landing/qna",
        element: <Navigate to="/home/voc" replace />,
      },
    ],
  },
]
