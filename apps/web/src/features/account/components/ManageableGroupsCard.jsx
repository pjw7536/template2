import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"

function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR")
}

export function ManageableGroupsCard({ groups }) {
  if (!groups?.length) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle>관리 가능한 그룹</CardTitle>
          <CardDescription>현재 사용자가 관리 가능한 user_sdwt_prod 목록입니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">관리 가능한 그룹이 없습니다.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>관리 가능한 그룹</CardTitle>
        <CardDescription>그룹별 멤버와 권한 상태를 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {groups.map((group, index) => (
          <div key={group.userSdwtProd} className="grid gap-2">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-foreground">{group.userSdwtProd}</h4>
              <Badge variant="secondary">관리</Badge>
            </div>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>사용자</TableHead>
                    <TableHead>권한</TableHead>
                    <TableHead>부여 시각</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {group.members?.length ? (
                    group.members.map((member) => (
                      <TableRow key={`${group.userSdwtProd}-${member.userId}`}>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium">{member.username || "미지정"}</span>
                            {member.name ? (
                              <span className="text-muted-foreground text-xs">{member.name}</span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell>
                          {member.canManage ? (
                            <Badge variant="default">관리자</Badge>
                          ) : (
                            <Badge variant="outline">멤버</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(member.grantedAt)}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">
                        멤버가 없습니다.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            {index < groups.length - 1 ? <Separator /> : null}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
