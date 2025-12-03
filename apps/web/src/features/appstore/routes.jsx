// src/features/appstore/routes.jsx
// Appstore feature가 제공하는 라우트 정의를 외부에 노출합니다.
import { AppstoreLayout } from "./components/AppstoreLayout"
import { AppstorePage } from "./pages/AppstorePage"

export const appstoreRoutes = [
  {
    path: "appstore",
    element: <AppstoreLayout />,
    children: [
      {
        index: true,
        element: <AppstorePage />,
      },
    ],
  },
]
