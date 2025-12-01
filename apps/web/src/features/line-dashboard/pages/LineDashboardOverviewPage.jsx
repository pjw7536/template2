// src/features/line-dashboard/pages/LineDashboardOverviewPage.jsx
// 공정 요약을 붙일 개요 페이지입니다.
import { useEffect, useMemo, useState } from "react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { getAirflowDagOverview } from "@/features/line-dashboard/api/get-airflow-dag-overview"

function formatDate(dateLike) {
  if (!dateLike) return "—"
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function getStatusBadge(dag) {
  if (dag.isPaused) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-400/20 dark:text-amber-200">
        Paused
      </span>
    )
  }

  return (
    <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200">
      Active
    </span>
  )
}

function getRunBadge(run) {
  if (!run?.state) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700/40 dark:text-slate-200">
        No runs
      </span>
    )
  }

  const normalized = run.state.toLowerCase()

  if (normalized === "success") {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-200">
        Success
      </span>
    )
  }

  if (normalized === "failed") {
    return (
      <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-400/20 dark:text-rose-200">
        Failed
      </span>
    )
  }

  return (
    <span className="inline-flex items-center rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700 dark:bg-sky-400/20 dark:text-sky-200">
      {run.state}
    </span>
  )
}

function renderTagList(tags) {
  if (!tags?.length) return <span className="text-xs text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
        >
          {tag}
        </span>
      ))}
    </div>
  )
}

function renderOwnerList(owners) {
  if (!owners?.length) return <span className="text-xs text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {owners.map((owner) => (
        <span
          key={owner}
          className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700/40 dark:text-slate-200"
        >
          {owner}
        </span>
      ))}
    </div>
  )
}

const initialState = { status: "idle", overview: null, error: null }

export function LineDashboardOverviewPage() {
  const [{ status, overview, error }, setState] = useState(initialState)

  useEffect(() => {
    let active = true

    async function loadOverview() {
      setState({ status: "loading", overview: null, error: null })
      try {
        const result = await getAirflowDagOverview()
        if (!active) return
        if (result?.error) {
          setState({ status: "error", overview: result, error: result.error })
        } else {
          setState({ status: "success", overview: result, error: null })
        }
      } catch (err) {
        if (!active) return
        setState({ status: "error", overview: null, error: err?.message ?? "Airflow DAG 정보를 불러오지 못했습니다." })
      }
    }

    loadOverview()
    return () => {
      active = false
    }
  }, [])

  const dags = useMemo(() => overview?.dags ?? [], [overview])
  const totals = overview?.totals ?? { total: 0, active: 0, paused: 0, failed: 0 }

  if (status === "loading") {
    return (
      <section className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Airflow DAG Overview</CardTitle>
            <CardDescription>Loading Airflow metadata...</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">잠시만 기다려 주세요.</p>
          </CardContent>
        </Card>
      </section>
    )
  }

  if (status === "error" || overview?.error || error) {
    return (
      <section className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Airflow DAG Overview</CardTitle>
            <CardDescription>
              Airflow API 에 접근하는 동안 오류가 발생했습니다. 설정을 확인해 주세요.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-destructive">{error || overview?.error}</p>
            <p className="text-sm text-muted-foreground">
              Airflow 이 <code className="rounded bg-muted px-1 py-0.5">{overview?.baseUrl}</code>
              에서 실행 중인지, 필요한 경우 <code>AIRFLOW_USERNAME</code> 과 <code>AIRFLOW_PASSWORD</code>
              환경 변수가 설정되어 있는지 확인하세요.
            </p>
          </CardContent>
        </Card>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Total DAGs</CardDescription>
            <CardTitle className="text-3xl font-semibold">{totals.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Active</CardDescription>
            <CardTitle className="text-3xl font-semibold text-emerald-600 dark:text-emerald-300">
              {totals.active}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Paused</CardDescription>
            <CardTitle className="text-3xl font-semibold text-amber-600 dark:text-amber-300">
              {totals.paused}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Last Run Failed</CardDescription>
            <CardTitle className="text-3xl font-semibold text-rose-600 dark:text-rose-300">
              {totals.failed}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card className="h-full">
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <CardTitle>Airflow DAG Overview</CardTitle>
            <CardDescription>
              Airflow 에서 제공한 DAG 목록과 최근 실행 결과를 확인할 수 있습니다.
            </CardDescription>
          </div>
          <p className="text-xs text-muted-foreground">
            Last updated: {formatDate(overview?.fetchedAt)}
          </p>
        </CardHeader>
        <CardContent className="pb-6">
          <TableContainer>
            <Table stickyHeader>
              <TableHeader>
                <TableRow>
                  <TableHead>DAG</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Latest Run</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Owners</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead>Next Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dags.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                      등록된 DAG 가 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  dags.map((dag, index) => {
                    const airflowDagUrl = `${overview?.baseUrl}/dags/${encodeURIComponent(dag.dagId)}/grid`
                    const latestExecution = dag.latestRun?.executionDate
                    return (
                      <TableRow key={dag.dagId || `dag-${index}`}>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <a
                              href={airflowDagUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-primary hover:underline"
                            >
                              {dag.dagId || "(unnamed)"}
                            </a>
                            {dag.description && (
                              <span className="text-xs text-muted-foreground">{dag.description}</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{getStatusBadge(dag)}</TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            {getRunBadge(dag.latestRun)}
                            {latestExecution && (
                              <span className="text-xs text-muted-foreground">
                                {formatDate(latestExecution)}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs text-muted-foreground">
                            {dag.timetable || "—"}
                          </span>
                        </TableCell>
                        <TableCell>{renderOwnerList(dag.owners)}</TableCell>
                        <TableCell>{renderTagList(dag.tags)}</TableCell>
                        <TableCell>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(dag.nextRun) || "—"}
                          </span>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </section>
  )
}
