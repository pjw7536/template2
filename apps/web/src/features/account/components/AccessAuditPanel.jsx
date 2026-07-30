import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/common"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"

import { formatAccountDateValue } from "../utils/accountOverview"
import {
  ACCESS_ACTION_LABELS,
  formatPermissionCount,
  getAuditChanges,
  getAuditIdentity,
} from "../utils/permissionDisplay"
import { PermissionErrorState, PermissionPager } from "./PermissionPanelStates"


export function AccessAuditPanel({ query, scope, scopeOptions, onScopeChange, onPageChange }) {
  const rows = query.data?.results || []

  return (
    <Card className="grid h-full min-h-0 min-w-0 grid-rows-[min-content_minmax(0,1fr)] gap-0 overflow-hidden py-0">
      <CardHeader className="grid-rows-[auto] content-start border-b px-4 py-3 pb-3!">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">변경 이력</CardTitle>
            <CardDescription>
              {formatPermissionCount(query.data?.pagination?.total)}건
            </CardDescription>
          </div>
          <Select value={scope} onValueChange={onScopeChange}>
            <SelectTrigger className="w-48" aria-label="권한 범위 필터">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scopeOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)_auto] p-0">
        {query.isPending ? (
          <div className="grid gap-2 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : query.error ? (
          <div className="p-4">
            <PermissionErrorState error={query.error} onRetry={query.refetch} />
          </div>
        ) : !rows.length ? (
          <div className="p-4 text-sm text-muted-foreground">표시할 변경 이력이 없습니다.</div>
        ) : (
          <div className="min-h-0 min-w-0 overflow-auto" aria-busy={query.isFetching}>
            <Table stickyHeader>
              <TableHeader>
                <TableRow>
                  <TableHead>시각</TableHead>
                  <TableHead>작업</TableHead>
                  <TableHead>대상</TableHead>
                  <TableHead>핵심 변경</TableHead>
                  <TableHead>작업자</TableHead>
                  <TableHead>사유</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const changes = getAuditChanges(row)
                  const target = row.targetUser
                    ? getAuditIdentity(row.targetUser)
                    : row.affiliation?.userSdwtProd
                      || row.policyRule?.value
                      || row.scope
                      || row.after?.value
                      || row.before?.value
                      || "-"
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="min-w-40 text-xs text-muted-foreground">
                        {formatAccountDateValue(row.createdAt)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {ACCESS_ACTION_LABELS[row.action] || row.action}
                        </Badge>
                      </TableCell>
                      <TableCell className="min-w-36">{target}</TableCell>
                      <TableCell>
                        <div className="flex min-w-60 flex-col gap-1">
                          {changes.length ? changes.map((change) => (
                            <span key={change} className="text-xs text-muted-foreground">
                              {change}
                            </span>
                          )) : <span className="text-xs text-muted-foreground">-</span>}
                        </div>
                      </TableCell>
                      <TableCell className="min-w-32">{getAuditIdentity(row.actor)}</TableCell>
                      <TableCell className="max-w-sm whitespace-normal break-words text-sm text-muted-foreground">
                        {row.reason || "-"}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
        <PermissionPager
          pagination={query.data?.pagination}
          onPageChange={onPageChange}
          disabled={query.isFetching}
        />
      </CardContent>
    </Card>
  )
}
