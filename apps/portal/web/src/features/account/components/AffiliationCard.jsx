import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function AffiliationCard({ data }) {
  return (
    <Card className="h-full min-h-0 gap-0 overflow-hidden py-0">
      <CardHeader className="shrink-0 border-b px-5 py-4">
        <CardTitle>등록 소속</CardTitle>
        <CardDescription>사용자 등록 시 저장한 소속입니다. 접근 권한은 별도로 관리됩니다.</CardDescription>
      </CardHeader>
      <CardContent className="min-h-0 min-w-0 flex-1 overflow-y-auto p-5">
        <dl className="grid gap-4 text-sm">
          <div><dt className="text-muted-foreground">SDWT</dt><dd>{data?.currentUserSdwtProd || "소속 없음"}</dd></div>
          <div><dt className="text-muted-foreground">Line</dt><dd>{data?.currentLine || "—"}</dd></div>
          <div><dt className="text-muted-foreground">부서</dt><dd>{data?.currentDepartment || "—"}</dd></div>
        </dl>
      </CardContent>
    </Card>
  )
}
