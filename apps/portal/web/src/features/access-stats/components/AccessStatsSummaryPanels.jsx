import { Crown, FileSpreadsheet, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import {
  TOP_RANK_CLASSES,
  formatNumber,
  formatSourceLabel,
} from "../utils/accessStatsPage"

export function KpiCard({ title, value, description, icon: Icon, isLoading }) {
  return (
    <Card className="h-full min-h-0 gap-0.5 rounded-lg px-3 py-1.5 shadow-none items-start justify-start p-4 gap-2">
      <div className="flex min-w-0 items-start justify-between gap-2">
        <span className="truncate text-xs font-medium leading-none text-muted-foreground">{title}</span>
        <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      </div>
      {isLoading ? (
        <Skeleton className="h-5 w-20" />
      ) : (
        <div className="truncate text-base font-semibold leading-5 tabular-nums tracking-tight">{value}</div>
      )}
      <p className="truncate text-[11px] leading-3 text-muted-foreground">{description}</p>
    </Card>
  )
}
export function StatePanel({ icon: Icon, title, description, action }) {
  return (
    <div className="flex h-full min-h-64 items-center justify-center rounded-lg border bg-card p-8 text-center">
      <div className="grid max-w-md justify-items-center gap-3">
        <Icon className="size-8 text-muted-foreground" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
    </div>
  )
}

export function AppTable({ apps, isLoading }) {
  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col gap-0 overflow-hidden rounded-lg py-0 shadow-none">
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-4">
        <CardTitle className="text-sm font-semibold">앱별 접속 순위 및 상세 현황</CardTitle>
        <Badge variant="secondary" className="h-5 px-1.5 py-0 text-[11px]">
          {formatNumber(apps.length)} apps
        </Badge>
      </div>
      <CardContent className="flex min-h-0 min-w-0 flex-1 flex-col items-stretch justify-start overflow-auto px-0 py-0">
        {isLoading ? (
          <div className="grid gap-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <Table className="table-fixed">
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow className="hover:bg-transparent">
                <TableHead className="h-12 w-1/2 px-4 text-left">앱명</TableHead>
                <TableHead className="h-12 w-1/4 text-center">출처</TableHead>
                <TableHead className="h-12 w-1/4 px-4 text-center">접속횟수</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {apps.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="h-32 text-center text-muted-foreground">
                    선택한 기간에 접속 기록이 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                apps.map((app, index) => (
                  <TableRow key={app.appId}>
                    <TableCell className="w-1/2 px-4">
                      <div className="flex min-w-0 items-center gap-2">
                        <span
                          className={cn(
                            "inline-flex h-6 min-w-6 shrink-0 items-center justify-center gap-0.5 rounded-md border bg-muted px-1 text-xs font-medium tabular-nums",
                            TOP_RANK_CLASSES[index]
                          )}
                        >
                          {index === 0 ? <Crown className="size-3" aria-label="1위" /> : null}
                          {index + 1}
                        </span>
                        <span className="min-w-0 truncate font-medium">{app.appName}</span>
                      </div>
                    </TableCell>
                    <TableCell className="w-1/4 text-center">
                      <Badge variant={app.sourceType === "manual" ? "outline" : "secondary"}>
                        {formatSourceLabel(app)}
                      </Badge>
                    </TableCell>
                    <TableCell className="w-1/4 px-4 text-center tabular-nums">
                      {formatNumber(app.accessCount)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

export function KpiActionCard({ onManualInput, onExternalSync, canManageStats, isSyncing, syncLabel }) {
  return (
    <Card className="h-full min-h-0 justify-center gap-2 rounded-lg px-3 py-2 shadow-none">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 justify-start text-[11px]"
        onClick={onManualInput}
        disabled={!canManageStats}
      >
        <FileSpreadsheet className="size-4" />
        외부 앱 수동입력
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 justify-start text-[11px]"
        onClick={onExternalSync}
        disabled={isSyncing}
      >
        <RefreshCw className={cn("size-4", isSyncing && "animate-spin")} />
        {syncLabel}
      </Button>
    </Card>
  )
}
