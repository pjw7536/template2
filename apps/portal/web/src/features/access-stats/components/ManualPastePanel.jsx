import { useState } from "react"
import { CheckCircle2, ClipboardPaste, Download } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

import {
  useManualAppAccessCommitMutation,
  useManualAppAccessPreviewMutation,
} from "../hooks/useAccessStatsQueries"
import {
  buildManualPasteSample,
  downloadManualTemplateCsv,
  formatNumber,
} from "../utils/accessStatsPage"

function hasPreviewErrors(preview) {
  if (!preview) return false
  if (Array.isArray(preview.errors) && preview.errors.length > 0) return true
  return preview.rows?.some((row) => row.errors?.length > 0) ?? false
}

export function ManualPastePanel({ onCommitted }) {
  const [pastedText, setPastedText] = useState("")
  const [sourceName, setSourceName] = useState("manual")
  const [preview, setPreview] = useState(null)
  const previewMutation = useManualAppAccessPreviewMutation({
    onSuccess: (payload) => setPreview(payload),
  })
  const commitMutation = useManualAppAccessCommitMutation({
    onSuccess: (payload) => {
      setPreview(payload)
      onCommitted?.()
    },
  })

  const errorPreview = commitMutation.error?.payload?.preview ?? null
  const visiblePreview = errorPreview ?? preview
  const previewHasErrors = hasPreviewErrors(visiblePreview)
  const previewRows = visiblePreview?.rows ?? []
  const canPreview = pastedText.trim().length > 0 && !previewMutation.isPending
  const canCommit =
    pastedText.trim().length > 0 &&
    visiblePreview &&
    previewRows.length > 0 &&
    !previewHasErrors &&
    !commitMutation.isPending

  function handlePreview() {
    previewMutation.mutate({ pastedText, sourceName })
  }

  function handleCommit() {
    commitMutation.mutate({ pastedText, sourceName })
  }

  function handleTextChange(value) {
    setPastedText(value)
    setPreview(null)
    previewMutation.reset()
    commitMutation.reset()
  }

  function handlePaste(event) {
    const nextText = event.clipboardData?.getData("text") ?? ""
    if (!nextText.trim()) return

    event.preventDefault()
    handleTextChange(nextText)
    previewMutation.mutate({ pastedText: nextText, sourceName })
  }

  return (
    <div className="grid gap-4">
      {visiblePreview ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Badge variant={previewHasErrors ? "destructive" : "secondary"}>
            오류 {formatNumber(visiblePreview.summary?.errorRows)}
          </Badge>
          <Badge variant="outline">유효 {formatNumber(visiblePreview.summary?.validRows)}행</Badge>
        </div>
      ) : null}

      <div className="rounded-lg border bg-card">
        <div className="grid gap-4 p-4">
          <div className="grid gap-4 lg:grid-cols-[220px,1fr]">
            <div className="grid content-start gap-2">
              <Label htmlFor="manual-source-name">출처</Label>
              <Input
                id="manual-source-name"
                value={sourceName}
                onChange={(event) => {
                  setSourceName(event.target.value)
                  setPreview(null)
                  previewMutation.reset()
                  commitMutation.reset()
                }}
                placeholder="manual"
              />
              <p className="text-xs leading-5 text-muted-foreground">
                같은 앱/날짜/출처는 기존 값을 덮어씁니다.
              </p>
            </div>
            <div className="grid min-w-0 gap-2">
              <Label htmlFor="manual-paste-text">붙여넣기 데이터</Label>
              <Textarea
                id="manual-paste-text"
                value={pastedText}
                onChange={(event) => handleTextChange(event.target.value)}
                onPaste={handlePaste}
                placeholder={buildManualPasteSample()}
                className="min-h-28 font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              필수 컬럼: date, appName, accessCount, uniqueUserCount
            </p>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={downloadManualTemplateCsv}>
                <Download className="size-4" />
                템플릿 CSV
              </Button>
              <Button type="button" variant="outline" onClick={handlePreview} disabled={!canPreview}>
                <ClipboardPaste className={cn("size-4", previewMutation.isPending && "animate-pulse")} />
                미리보기
              </Button>
              <Button type="button" onClick={handleCommit} disabled={!canCommit}>
                <CheckCircle2 className="size-4" />
                반영
              </Button>
            </div>
          </div>

          {previewMutation.error ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {previewMutation.error.message}
            </div>
          ) : null}
          {commitMutation.error ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {commitMutation.error.message}
            </div>
          ) : null}
          {commitMutation.data?.commit ? (
            <div className="rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
              신규 {formatNumber(commitMutation.data.commit.createdRows)}건, 수정{" "}
              {formatNumber(commitMutation.data.commit.updatedRows)}건을 반영했습니다.
            </div>
          ) : null}

          {visiblePreview?.errors?.length ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {visiblePreview.errors.join(", ")}
            </div>
          ) : null}

          {visiblePreview ? (
            <div className="min-h-0 min-w-0 overflow-auto rounded-md border">
              <Table>
                <TableHeader className="bg-card">
                  <TableRow>
                    <TableHead className="w-16 px-4">행</TableHead>
                    <TableHead>날짜</TableHead>
                    <TableHead>앱</TableHead>
                    <TableHead className="text-right">접속횟수</TableHead>
                    <TableHead className="text-right">접속 사용자</TableHead>
                    <TableHead>상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewRows.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                        미리보기할 데이터 행이 없습니다.
                      </TableCell>
                    </TableRow>
                  ) : (
                    previewRows.map((row) => {
                      const rowHasErrors = row.errors?.length > 0
                      return (
                        <TableRow key={row.rowNumber}>
                          <TableCell className="px-4 text-muted-foreground tabular-nums">
                            {row.rowNumber}
                          </TableCell>
                          <TableCell className="tabular-nums">{row.values?.date || "-"}</TableCell>
                          <TableCell>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{row.values?.appName || "-"}</p>
                              <p className="text-xs text-muted-foreground">{row.values?.appId || "-"}</p>
                            </div>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(row.values?.accessCount)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(row.values?.uniqueUserCount)}
                          </TableCell>
                          <TableCell>
                            {rowHasErrors ? (
                              <span className="text-sm text-destructive">{row.errors.join(", ")}</span>
                            ) : (
                              <Badge variant="secondary">정상</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
