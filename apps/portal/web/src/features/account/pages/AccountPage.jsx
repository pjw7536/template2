import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth"

const roleLabels = { viewer: "조회", user: "조회·수정", admin: "조회·수정·삭제" }

export default function AccountPage() {
  const { user } = useAuth()
  if (!user) return null
  const scopes = Object.entries(user.scopeAccess || {}).filter(([key]) => key !== "portal")
  const sdwts = Object.entries(user.sdwtAccess || {})
  return (
    <div className="h-full min-h-0 overflow-y-auto px-6 py-4">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        <h2 className="text-2xl font-semibold tracking-tight">내 계정과 접근 권한</h2>
        <p className="text-sm text-muted-foreground">소속과 권한은 Keycloak에서 관리합니다. 변경이 필요하면 관리자에게 요청하세요. 변경된 권한은 다음 로그인부터 적용됩니다.</p>
        <Card>
          <CardHeader><CardTitle>사용자 정보</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto,1fr] gap-x-6 gap-y-2 text-sm">
              {[["이름", user.username], ["EPID", user.avatarId], ["Knox ID", user.knoxId], ["부서", user.department], ["Line", user.line], ["소속 SDWT", user.userSdwtProd]].map(([label, value]) => (
                <div key={label} className="contents"><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{value || "미지정"}</dd></div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>앱 접근</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {user.isPortalAdmin ? <p>전체 관리자: 모든 앱과 데이터에 접근할 수 있습니다.</p> : user.hasAllAppsAccess ? <p>전체 앱 사용 역할: 모든 활성 앱을 사용할 수 있습니다. 데이터 범위는 아래 SDWT 권한을 따릅니다.</p> : null}
            <ul className="divide-y">{scopes.map(([key, access]) => <li key={key} className="flex justify-between gap-4 py-2"><span>{key}</span><span className="text-muted-foreground">{access.allowed ? access.role === "admin" ? "관리 기능 사용" : "사용 가능" : "권한 없음"}</span></li>)}</ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>SDWT 데이터 범위</CardTitle></CardHeader>
          <CardContent className="text-sm">
            {user.isPortalAdmin ? <p>모든 SDWT의 데이터 작업이 허용됩니다.</p> : sdwts.length ? <ul className="divide-y">{sdwts.map(([sdwt, role]) => <li key={sdwt} className="flex justify-between gap-4 py-2"><span>{sdwt}</span><span className="text-muted-foreground">{roleLabels[role]}</span></li>)}</ul> : <p className="text-muted-foreground">부여된 SDWT 데이터 권한이 없습니다.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
