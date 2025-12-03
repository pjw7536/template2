// src/features/home/routes.jsx
// 홈 화면 라우트 설정을 정의합니다.
import { HomePage } from "./pages/HomePage"

export const homeRoutes = [
  {
    path: "ESOP_Dashboard/Home",
    element: <HomePage />,
  },
  {
    path: "/",
    element: <HomePage />,
  },
]
