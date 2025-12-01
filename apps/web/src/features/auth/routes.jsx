// src/features/auth/routes.jsx
// 인증 관련 라우트를 정의합니다.
import { LoginPage } from "./pages/LoginPage"

export const authRoutes = [
  {
    path: "/login",
    element: <LoginPage />,
  },
]
