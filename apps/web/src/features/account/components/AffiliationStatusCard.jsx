import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

function InfoRow({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value || "미지정"}</span>
    </div>
  )
}

export function AffiliationStatusCard({ affiliation, reconfirm }) {
  const needsReconfirm = Boolean(reconfirm?.requiresReconfirm)
  const predicted = reconfirm?.predictedUserSdwtProd || null

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>현재 소속</CardTitle>
        <CardDescription>현재 적용 중인 소속 정보를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-3 rounded-lg border p-3">
          <InfoRow label="Department" value={affiliation?.currentDepartment} />
          <InfoRow label="Line" value={affiliation?.currentLine} />
          <InfoRow label="user_sdwt_prod" value={affiliation?.currentUserSdwtProd} />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">재확인 상태</span>
            {needsReconfirm ? (
              <Badge variant="destructive">재확인 필요</Badge>
            ) : (
              <Badge variant="secondary">정상</Badge>
            )}
          </div>
          {predicted ? (
            <p className="text-sm text-muted-foreground">
              외부 예측 소속: <span className="font-medium text-foreground">{predicted}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">외부 예측 소속 정보가 없습니다.</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
