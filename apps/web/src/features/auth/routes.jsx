// src/features/auth/routes.jsx
// 인증 관련 라우트를 정의합니다.
import { lazyNamed } from "@/lib/react/lazyNamed"

const LoginPage = lazyNamed(() => import("./pages/LoginPage"), "LoginPage")

export const authRoutes = [
  {
    path: "login",
    element: <LoginPage />,
  },
]
