import { Suspense } from "react"

import { CenteredPage, LoginForm } from "@/features/auth"

export default function Page() {
  return (
    <Suspense
      fallback={
        <CenteredPage>
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <p className="text-sm text-muted-foreground">로그인 페이지를 불러오는 중입니다...</p>
          </div>
        </CenteredPage>
      }
    >
      <CenteredPage>
        <LoginForm />
      </CenteredPage>
    </Suspense>
  )
}
