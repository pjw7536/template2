// src/features/line-dashboard/components/DataTableColumnRenderers.jsx
// 컬럼별로 서로 다른 UI 표현을 담당하는 렌더러 모음입니다.
import { ExternalLink, Check, AlertTriangle } from "lucide-react"

import { CommentCell } from "./CommentCell"
import { NeedToSendCell } from "./NeedToSendCell"
import { formatCellValue } from "../utils/dataTableFormatters"
import { STATUS_LABELS } from "../utils/statusLabels"
import {
  buildJiraBrowseUrl,
  getRecordId,
  normalizeComment,
  normalizeJiraKey,
  normalizeNeedToSend,
  normalizeStatus,
  toHttpUrl,
} from "../utils/dataTableColumnNormalizers"
import { computeMetroProgress } from "../utils/dataTableColumnProcessFlow"
import { deriveFlagState } from "../utils/dataTableFlagState"

const CellRenderers = {
  defect_url: ({ value }) => {
    const href = toHttpUrl(value)
    if (!href) return null
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center text-primary transition-colors hover:text-primary/80"
        aria-label="Open defect URL in a new tab"
        title="Open defect"
      >
        <ExternalLink className="h-4 w-4" />
      </a>
    )
  },

  jira_key: ({ value }) => {
    const key = normalizeJiraKey(value)
    const href = buildJiraBrowseUrl(key)
    if (!href || !key) return null
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-primary transition-colors hover:text-primary/80"
        aria-label={`Open JIRA issue ${key} in a new tab`}
        title={key}
      >
        <ExternalLink className="h-4 w-4" />
      </a>
    )
  },

  comment: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    return (
      <CommentCell
        meta={meta}
        recordId={recordId}
        baseValue={normalizeComment(rowOriginal?.comment)}
      />
    )
  },

  needtosend: ({ value, rowOriginal, meta }) => {
    const recordId = getRecordId(rowOriginal)
    if (!meta || !recordId) return formatCellValue(value)
    const baseState = deriveFlagState(normalizeNeedToSend(rowOriginal?.needtosend), 0)
    const isLocked = deriveFlagState(rowOriginal?.send_jira, 0).isOn
    return (
      <NeedToSendCell
        meta={meta}
        recordId={recordId}
        baseValue={baseState.numericValue}
        state={baseState}
        disabled={isLocked}
        disabledReason="이미 JIRA 전송됨 (needtosend 수정 불가)"
      />
    )
  },

  send_jira: ({ value }) => {
    const { state, numericValue, isOn } = deriveFlagState(value, 0)
    const title =
      state === "error"
        ? `JIRA 전송 오류 상태 (값: ${numericValue})`
        : isOn
          ? "Sent to JIRA"
          : "Not sent"
    return (
      <span
        className={[
          "inline-flex h-5 w-5 items-center justify-center rounded-full border text-muted-foreground transition-colors",
          state === "error"
            ? "border-destructive/60 bg-destructive/10 text-destructive"
            : isOn
              ? "bg-primary border-primary text-primary-foreground"
              : "border-border",
        ].join(" ")}
        title={title}
        aria-label={title}
        role="img"
      >
        {state === "error" ? (
          <AlertTriangle className="h-3 w-3" strokeWidth={3} />
        ) : isOn ? (
          <Check className="h-3 w-3" strokeWidth={3} />
        ) : null}
      </span>
    )
  },

  status: ({ value, rowOriginal }) => {
    const status = normalizeStatus(value)
    const label = STATUS_LABELS[status] ?? status ?? "Unknown"
    const { completed, total } = computeMetroProgress(rowOriginal, status)
    const percent = total > 0 ? Math.min(100, Math.max(0, (completed / total) * 100)) : 0

    return (
      <div className="flex w-full flex-col gap-1">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Number.isFinite(percent) ? Math.round(percent) : 0}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuetext={`${completed} of ${total} steps`}
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${percent}%` }}
            role="presentation"
          />
        </div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span className="truncate" title={label}>
            {label}
          </span>
          <span>
            {completed}
            <span aria-hidden="true">/</span>
            {total}
          </span>
        </div>
      </div>
    )
  },
}

// 컬럼 키에 맞는 렌더러를 찾아 실행하고, 없으면 기본 포맷터를 사용합니다.
export function renderCellByKey(colKey, info) {
  const meta = info.table?.options?.meta
  const value = info.getValue()
  const rowOriginal = info.row?.original
  const renderer = CellRenderers[colKey]
  if (renderer) return renderer({ value, rowOriginal, meta })
  return formatCellValue(value)
}
