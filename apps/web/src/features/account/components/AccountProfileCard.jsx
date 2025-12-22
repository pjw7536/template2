import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const ROLE_LABELS = {
  admin: "Admin",
  manager: "Manager",
  viewer: "Viewer",
}

function InfoRow({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value || "미지정"}</span>
    </div>
  )
}

export function AccountProfileCard({ profile }) {
  const roleKey = (profile?.role || "").toLowerCase()
  const roleLabel = ROLE_LABELS[roleKey] || profile?.role || "미지정"
  const statusBadges = [
    profile?.isSuperuser ? "슈퍼유저" : null,
    profile?.isStaff ? "스태프" : null,
  ].filter(Boolean)

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>사용자 기본 정보</CardTitle>
        <CardDescription>로그인 사용자 기준 계정 메타 정보를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-3 rounded-lg border p-3">
          <InfoRow label="Username" value={profile?.username} />
          <InfoRow label="Knox ID" value={profile?.knoxId} />
          <InfoRow label="Role" value={roleLabel} />
          <InfoRow label="user_sdwt_prod" value={profile?.userSdwtProd} />
        </div>
        {statusBadges.length ? (
          <div className="flex flex-wrap gap-2">
            {statusBadges.map((label) => (
              <Badge key={label} variant="secondary">
                {label}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
