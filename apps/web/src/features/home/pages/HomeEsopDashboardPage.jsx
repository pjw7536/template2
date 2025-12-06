import { RequireAuth } from "@/lib/auth"
import { LineDashboardEntryPage } from "@/features/line-dashboard"

const HomeEsopDashboardPage = () => {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="space-y-6">
        <header className="space-y-2">
          <p className="text-sm font-medium text-primary">E-SOP Dashboard</p>
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold tracking-tight">라인별 대시보드에 바로 진입</h1>
            <p className="text-sm text-muted-foreground">
              로그인 후 자동으로 연결 가능한 라인으로 이동합니다. 접근 권한이 없다면 계정으로 먼저 로그인해 주세요.
            </p>
          </div>
        </header>

        <RequireAuth>
          <LineDashboardEntryPage />
        </RequireAuth>
      </div>
    </div>
  )
}

export default HomeEsopDashboardPage
