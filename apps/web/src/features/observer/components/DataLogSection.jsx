// src/features/observer/components/DataLogSection.jsx
import React from "react";
import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import ObserverDataTable from "./ObserverDataTable";
import { LoadingSpinner } from "./Loaders";
import { getLogTypeBadgeClass } from "../utils/logTypeStyles";
import { OBSERVER_LOG_CONFIG } from "../utils/logPagination";

export default function DataLogSection({
  eqpId,
  logsLoading,
  tableData,
  typeFilters,
  handleFilter,
  logErrors = [],
  onRetryLogs,
  hasMoreByType = {},
  onLoadMoreType,
  loadingMoreTypes = new Set(),
  residentLogCount = 0,
  residentLimitReached = false,
  evidenceNavigationStatus = null,
}) {
  const hasLogErrors = logErrors.length > 0;
  const moreTypes = OBSERVER_LOG_CONFIG.filter(
    ({ logKey }) => hasMoreByType[logKey]
  );

  return (
    <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex-[2] h-120 min-h-0 flex flex-col overflow-hidden">
      {!eqpId && !logsLoading ? (
        <p className="text-center text-sm text-muted-foreground py-4">
          EQP를 선택하세요.
        </p>
      ) : logsLoading ? (
        <div className="flex items-center justify-center h-full">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          {evidenceNavigationStatus ? (
            <div
              className={[
                "mb-2 flex items-center gap-2 rounded-md border px-3 py-2 text-xs",
                ["not_found", "error"].includes(evidenceNavigationStatus.status)
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-primary/20 bg-primary/5 text-foreground",
              ].join(" ")}
              role="status"
            >
              {evidenceNavigationStatus.status === "loading" ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : evidenceNavigationStatus.status === "found" ? (
                <CheckCircle2 className="size-3.5 text-primary" aria-hidden="true" />
              ) : (
                <TriangleAlert className="size-3.5" aria-hidden="true" />
              )}
              <span className="min-w-0 break-all">
                {evidenceNavigationStatus.status === "loading"
                  ? `AI 분석 근거 로그를 찾는 중입니다: ${evidenceNavigationStatus.evidenceId}`
                  : evidenceNavigationStatus.status === "found"
                    ? `AI 분석 근거 로그를 열었습니다: ${evidenceNavigationStatus.evidenceId}`
                    : evidenceNavigationStatus.status === "error"
                      ? `AI 분석 근거 로그 조회에 실패했습니다: ${evidenceNavigationStatus.evidenceId}`
                      : `원본 데이터에서 AI 분석 근거 로그를 찾지 못했습니다: ${evidenceNavigationStatus.evidenceId}`}
              </span>
              {evidenceNavigationStatus.status === "error" ? (
                <button
                  type="button"
                  onClick={() => evidenceNavigationStatus.retry?.()}
                  className="ml-auto shrink-0 rounded border border-destructive/30 px-2 py-1 font-medium hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  재시도
                </button>
              ) : null}
            </div>
          ) : null}
          {hasLogErrors ? (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <span>
                {logErrors.map((error) => error.type).join(", ")} 로그 조회에 실패했습니다.
              </span>
              {onRetryLogs ? (
                <button
                  type="button"
                  onClick={onRetryLogs}
                  className="shrink-0 rounded border border-destructive/30 px-2 py-1 font-medium hover:bg-destructive/10"
                >
                  재시도
                </button>
              ) : null}
            </div>
          ) : null}
          {moreTypes.length > 0 || residentLimitReached ? (
            <div className="mb-2 flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              <span className="mr-auto">
                {residentLogCount.toLocaleString()}건을 표시 중입니다.
                {residentLimitReached
                  ? " 안정적인 표시 한도에 도달해 기간을 좁혀야 합니다."
                  : " 이전 로그를 유형별로 추가 조회할 수 있습니다."}
              </span>
              {!residentLimitReached
                ? moreTypes.map(({ logKey, label }) => (
                    <button
                      key={logKey}
                      type="button"
                      onClick={() => onLoadMoreType?.(logKey)}
                      disabled={loadingMoreTypes.has(logKey)}
                      className="rounded-md border border-border bg-card px-2 py-1 font-medium text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loadingMoreTypes.has(logKey)
                        ? `${label} 조회 중`
                        : `${label} 더 불러오기`}
                    </button>
                  ))
                : null}
            </div>
          ) : null}
          <div className="min-h-0 flex-1">
            <ObserverDataTable
              data={tableData}
              typeFilters={typeFilters}
              handleFilter={handleFilter}
              getLogTypeBadgeClass={getLogTypeBadgeClass}
            />
          </div>
        </>
      )}
    </section>
  );
}
