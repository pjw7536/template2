import { useMemo, useState } from "react"
import { AlertTriangle, CalendarDays, Layers3, RefreshCw, ShieldAlert, TrendingUp } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useAuth } from "@/lib/auth"
import { hasScopeRole } from "@/lib/access/scopeAccess"

import {
  useAppAccessStatsQuery,
  useExternalAppUsageSyncMutation,
} from "../hooks/useAccessStatsQueries"
import {
  DEFAULT_ACCESS_DATE_OFFSET_DAYS,
  buildChartRows,
  buildRangeFromOffset,
  buildStatsParams,
  formatNumber,
  formatStatsRangeLabel,
} from "../utils/accessStatsPage"
import {
  AppTable,
  ChartPanel,
  KpiActionCard,
  KpiCard,
  ManualPastePanel,
  StatePanel,
} from "../components/AccessStatsPanels"

export function AccessStatsPage() {
  const { user } = useAuth()
  const [dateOffset, setDateOffset] = useState(DEFAULT_ACCESS_DATE_OFFSET_DAYS)
  const [periodKey, setPeriodKey] = useState("day")
  const [isManualDialogOpen, setIsManualDialogOpen] = useState(false)
  const params = useMemo(
    () => buildStatsParams(buildRangeFromOffset(dateOffset), periodKey),
    [dateOffset, periodKey]
  )
  const statsQuery = useAppAccessStatsQuery(params, { enabled: Boolean(user) })
  const externalSyncMutation = useExternalAppUsageSyncMutation({
    onSuccess: (result) => {
      if (!result?.skipped) return
      toast.info("동기화를 건너뛰었습니다.", {
        description: result.reason || "잠시 후 다시 시도해 주세요.",
      })
    },
  })
  const payload = statsQuery.data
  const summary = payload?.summary ?? {}
  const responsePeriod = payload?.period || periodKey
  const apps = useMemo(() => (Array.isArray(payload?.apps) ? payload.apps : []), [payload?.apps])
  const series = useMemo(() => (Array.isArray(payload?.series) ? payload.series : []), [payload?.series])
  const chartRows = useMemo(
    () => buildChartRows(series, apps, params, responsePeriod),
    [apps, params, responsePeriod, series]
  )
  const externalSyncLabel = externalSyncMutation.data?.skipped
    ? "최근 동기화됨"
    : externalSyncMutation.data?.synced
      ? "동기화 완료"
      : "외부 API 동기화"

  if (!user) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <StatePanel
          icon={ShieldAlert}
          title="로그인이 필요합니다."
          description="접속 현황은 로그인 후 볼 수 있습니다."
        />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <Dialog open={isManualDialogOpen} onOpenChange={setIsManualDialogOpen}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>외부 앱 수동 입력</DialogTitle>
            <DialogDescription>
              엑셀/스프레드시트에서 헤더 포함 영역을 복사해 붙여넣고 미리보기 후 반영합니다.
            </DialogDescription>
          </DialogHeader>
          <ManualPastePanel onCommitted={() => statsQuery.refetch()} />
        </DialogContent>
      </Dialog>

      <main className="flex-1 min-h-0 min-w-0 overflow-hidden px-6 py-4">
        <div className="grid h-full min-h-0 min-w-0 grid-cols-4 gap-4">
          <section className="col-span-3 flex h-full min-h-0 min-w-0 flex-col gap-4">
            <div className="grid h-24 shrink-0 grid-cols-7 gap-4">
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="전체 앱 개수"
                  value={formatNumber(summary.activeAppCount)}
                  description="접속 기록이 있는 앱"
                  icon={Layers3}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="전체 접속횟수"
                  value={formatNumber(summary.totalAccessCount)}
                  description={formatStatsRangeLabel(params)}
                  icon={TrendingUp}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-2 min-w-0">
                <KpiCard
                  title="최다 접속 앱"
                  value={summary.topApp?.appName || "-"}
                  description={
                    summary.topApp
                      ? `${formatNumber(summary.topApp.accessCount)}회`
                      : "접속 기록 없음"
                  }
                  icon={CalendarDays}
                  isLoading={statsQuery.isLoading}
                />
              </div>
              <div className="col-span-1 min-w-0">
                <KpiActionCard
                  onManualInput={() => setIsManualDialogOpen(true)}
                  onExternalSync={() => externalSyncMutation.mutate()}
                  canManageStats={hasScopeRole(user, "access-stats")}
                  isSyncing={externalSyncMutation.isPending}
                  syncLabel={externalSyncLabel}
                />
              </div>
            </div>

            {statsQuery.error ? (
              <StatePanel
                icon={AlertTriangle}
                title="접속 통계를 불러오지 못했습니다."
                description={statsQuery.error.message || "잠시 후 다시 시도하세요."}
                action={
                  <Button type="button" variant="outline" onClick={() => statsQuery.refetch()}>
                    <RefreshCw className="size-4" />
                    다시 시도
                  </Button>
                }
              />
            ) : (
              <div className="min-h-0 min-w-0 flex-1">
                <ChartPanel
                  apps={apps}
                  series={series}
                  range={params}
                  chartRows={chartRows}
                  isLoading={statsQuery.isLoading}
                  error={statsQuery.error}
                  period={responsePeriod}
                  dateOffset={dateOffset}
                  onDateOffsetChange={setDateOffset}
                  periodKey={periodKey}
                  onPeriodChange={setPeriodKey}
                />
              </div>
            )}
          </section>

          <section className="col-span-1 h-full min-h-0 min-w-0 overflow-hidden">
            <AppTable apps={apps} isLoading={statsQuery.isLoading} />
          </section>
        </div>
      </main>
    </div>
  )
}
