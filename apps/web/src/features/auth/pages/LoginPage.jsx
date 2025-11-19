// src/features/auth/pages/LoginPage.jsx
// 인증 전용 라우트에서 사용하는 로그인 화면입니다.
import { CenteredPage } from "../components/CenteredPage"
import { LoginForm } from "../components/LoginForm"

export function LoginPage() {
  return (
    <CenteredPage>
      <LoginForm />
    </CenteredPage>
  )
}
