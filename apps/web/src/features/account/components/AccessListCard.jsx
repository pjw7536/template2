import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

function AccessList({ items }) {
  if (!items?.length) {
    return <p className="text-sm text-muted-foreground">권한이 없습니다.</p>
  }

  return (
    <div className="grid gap-2">
      {items.map((item) => (
        <div
          key={`${item.userSdwtProd}-${item.source}`}
          className="flex items-center justify-between rounded-md border px-3 py-2"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">{item.userSdwtProd}</span>
            {item.source === "self" ? (
              <Badge variant="secondary">내 소속</Badge>
            ) : (
              <Badge variant="outline">부여됨</Badge>
            )}
          </div>
          {item.canManage ? <Badge variant="default">관리자</Badge> : null}
        </div>
      ))}
    </div>
  )
}

export function AccessListCard({ data }) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>메일함 접근</CardTitle>
        <CardDescription>
          user_sdwt_prod 단위로 메일함과 RAG 인덱스 접근 권한을 확인하세요.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-2">
          <h3 className="text-sm font-semibold text-foreground">접근 가능 목록</h3>
          <AccessList items={data?.accessibleUserSdwtProds} />
        </div>

        <Separator />

        <div className="grid gap-2">
          <h3 className="text-sm font-semibold text-foreground">관리 가능한 그룹</h3>
          {data?.manageableUserSdwtProds?.length ? (
            <div className="flex flex-wrap gap-2">
              {data.manageableUserSdwtProds.map((item) => (
                <Badge key={item} variant="secondary">
                  {item}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">관리 권한이 없습니다.</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
