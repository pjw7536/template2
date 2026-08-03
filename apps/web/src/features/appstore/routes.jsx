// src/features/appstore/routes.jsx
// Appstore feature가 제공하는 라우트 정의를 외부에 노출합니다.
import { lazyNamed } from "@/lib/react/lazyNamed"

const AppstoreShell = lazyNamed(() => import("./components/AppstoreShell"), "AppstoreShell")
const AppstorePage = lazyNamed(() => import("./pages/AppstorePage"), "AppstorePage")

export const appstoreRoutes = [
  {
    path: "appstore",
    element: <AppstoreShell />,
    children: [
      {
        index: true,
        element: <AppstorePage />,
      },
    ],
  },
]
