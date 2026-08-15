import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth"

function ReadOnlyField({ label, value }) {
  return (
    <div className="grid gap-1 border-b py-3 last:border-b-0">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm text-foreground">{value || "미지정"}</dd>
    </div>
  )
}

function RoleBadges({ roles }) {
  const values = Array.isArray(roles) ? roles : []
  if (values.length === 0) {
    return <p className="text-sm text-muted-foreground">부여된 역할이 없습니다.</p>
  }
  return (
    <div className="flex flex-wrap gap-2" aria-label="Keycloak 역할 목록">
      {values.map((role) => (
        <Badge key={role} variant={role.endsWith("-admin") ? "default" : "secondary"}>
          {role}
        </Badge>
      ))}
    </div>
  )
}

export default function AccountPage() {
  const { user } = useAuth()
  const affiliation = user?.user_sdwt_prod || "미지정"
  const clientRoles = Object.entries(user?.client_roles || {}).flatMap(([clientId, roles]) =>
    (Array.isArray(roles) ? roles : []).map((role) => `${clientId}:${role}`),
  )

  return (
    <div className="h-full min-h-0 overflow-y-auto px-6 py-4">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">내 계정</h2>
            <Badge variant="outline">Keycloak 관리</Badge>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">
            계정, 소속, 역할은 Keycloak에서 관리되며 이 화면에서는 조회만 할 수 있습니다.
          </p>
        </header>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card className="rounded-2xl">
            <CardHeader className="border-b px-4 py-3">
              <CardTitle className="text-sm font-semibold">내 정보</CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-1">
              <dl>
                <ReadOnlyField label="이름" value={user?.username} />
                <ReadOnlyField label="이메일" value={user?.email} />
                <ReadOnlyField label="Knox ID" value={user?.usr_id} />
                <ReadOnlyField label="Keycloak subject" value={user?.keycloak_subject} />
              </dl>
            </CardContent>
          </Card>

          <Card className="rounded-2xl">
            <CardHeader className="border-b px-4 py-3">
              <CardTitle className="text-sm font-semibold">기본 소속</CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-1">
              <dl>
                <ReadOnlyField label="소속" value={affiliation} />
                <ReadOnlyField label="Department" value={user?.department} />
                <ReadOnlyField label="Line" value={user?.line} />
                <ReadOnlyField label="Keycloak group ID" value={user?.keycloak_group_id} />
              </dl>
            </CardContent>
          </Card>
        </section>

        <Card className="rounded-2xl">
          <CardHeader className="border-b px-4 py-3">
            <CardTitle className="text-sm font-semibold">역할</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 p-4">
            <div className="grid gap-2">
              <p className="text-xs font-medium text-muted-foreground">Client roles</p>
              <RoleBadges roles={clientRoles} />
            </div>
            <div className="grid gap-2">
              <p className="text-xs font-medium text-muted-foreground">Realm roles</p>
              <RoleBadges roles={user?.realm_roles} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
