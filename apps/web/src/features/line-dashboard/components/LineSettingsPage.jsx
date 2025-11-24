// src/features/line-dashboard/components/LineSettingsPage.jsx
import * as React from "react"
import {
  IconDeviceFloppy,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconSettings,
  IconTrash,
  IconX,
} from "@tabler/icons-react"
import { AlertCircleIcon, BadgeCheckIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "components/ui/button"
import { Input } from "@/components/ui/input"
import { buildBackendUrl } from "@/lib/api"
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { timeFormatter } from "./data-table/utils/constants"
import { buildToastOptions } from "./data-table/utils/toast"

const LABELS = {
  titleSuffix: "Line E-SOP Settings",
  subtitle: "E-SOP가 종료 되기전에 미리 Inform할 Step을 설정합니다.",
  addTitle: "E-SOP Custom End Step 추가",
  mainStep: "Main Step",
  customEndStep: "Early Inform Step",
  lineId: "Line ID",
  updatedBy: "Updated By",
  updatedAt: "Updated At",
  addButton: "Add",
  refresh: "Refresh",
  updated: "Updated",
  loading: "Loading entries…",
  empty: "No overrides found for this line.",
  addDescription: "line_id는 선택한 값으로 자동 저장되며 수정할 수 없습니다.",
}

function normalizeUserSdwt(values) {
  if (!Array.isArray(values)) return []
  const deduped = new Set()
  return values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => {
      if (!value) return false
      if (deduped.has(value)) return false
      deduped.add(value)
      return true
    })
}

const SUCCESS_COLOR = "#065f46"
const INFO_COLOR = "#1e40af"
const ERROR_COLOR = "#991b1b"

function formatUpdatedAt(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })
}

function unwrapErrorMessage(message) {
  if (typeof message === "string") {
    try {
      const parsed = JSON.parse(message)
      if (parsed && typeof parsed.error === "string" && parsed.error.trim()) {
        return parsed.error
      }
    } catch {
      // noop
    }
    return message
  }
  return ""
}

function showCreateToast() {
  toast.success("추가 완료", {
    description: "새 조기 알림 설정이 저장되었습니다.",
    icon: <IconPlus className="h-5 w-5" />,
    ...buildToastOptions({ color: SUCCESS_COLOR }),
  })
}

function showUpdateToast() {
  toast.success("수정 완료", {
    description: "설정이 업데이트되었습니다.",
    icon: <IconDeviceFloppy className="h-5 w-5" />,
    ...buildToastOptions({ color: INFO_COLOR }),
  })
}

function showDeleteToast() {
  toast("삭제 완료", {
    description: "설정이 제거되었습니다.",
    icon: <IconTrash className="h-5 w-5" />,
    ...buildToastOptions({ color: ERROR_COLOR }),
  })
}

function showRequestErrorToast(message) {
  toast.error("요청 실패", {
    description: message || "요청 처리 중 오류가 발생했습니다.",
    icon: <IconX className="h-5 w-5" />,
    ...buildToastOptions({ color: ERROR_COLOR, duration: 3200 }),
  })
}

function normalizeEntry(entry, fallbackLineId = "") {
  if (!entry || typeof entry !== "object") return null
  const rawId = entry.id ?? entry?.ID
  if (rawId === null || rawId === undefined) return null

  const lineId =
    typeof entry.lineId === "string"
      ? entry.lineId
      : typeof entry.line_id === "string"
        ? entry.line_id
        : fallbackLineId

  const mainStepRaw =
    typeof entry.mainStep === "string"
      ? entry.mainStep
      : typeof entry.main_step === "string"
        ? entry.main_step
        : ""

  const customRaw =
    entry.customEndStep !== undefined
      ? entry.customEndStep
      : entry.custom_end_step

  const customEndStep =
    customRaw === null || customRaw === undefined
      ? ""
      : typeof customRaw === "string"
        ? customRaw
        : String(customRaw)

  const updatedBy =
    typeof entry.updatedBy === "string"
      ? entry.updatedBy
      : typeof entry.updated_by === "string"
        ? entry.updated_by
        : ""

  const updatedAtRaw = entry.updatedAt ?? entry.updated_at
  const updatedAt =
    typeof updatedAtRaw === "string" || typeof updatedAtRaw === "number"
      ? String(updatedAtRaw)
      : updatedAtRaw && typeof updatedAtRaw === "object" && typeof updatedAtRaw.toString === "function"
        ? updatedAtRaw.toString()
        : ""

  return {
    id: String(rawId),
    lineId,
    mainStep: mainStepRaw,
    customEndStep,
    updatedBy,
    updatedAt,
  }
}

function sortEntries(entries) {
  return [...entries].sort((a, b) =>
    a.mainStep.localeCompare(b.mainStep, undefined, { numeric: true, sensitivity: "base" })
  )
}

function LineUserSdwtBadges({ lineId, values }) {
  if (!lineId) {
    return (
      <div className="inline-flex items-center gap-2 rounded-md bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        라인을 선택하면 User SDWT 목록이 표시됩니다.
      </div>
    )
  }

  if (!values || values.length === 0) {
    return (
      <div className="inline-flex items-center gap-2 rounded-md bg-background px-2 py-1 text-[11px] text-muted-foreground">
        <AlertCircleIcon className="h-3 w-3" />
        등록된 User SDWT가 없습니다.
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-mono text-xs font-semibold text-foreground">{lineId} Line 분임조 : </span>
      {values.map((value) => (
        <Badge key={value} variant="secondary" className="gap-1 text-[11px] font-mono">
          <BadgeCheckIcon className="h-3 w-3" />
          {value}
        </Badge>
      ))}
    </div>
  )
}

export function LineSettingsPage({ lineId: initialLineId = "" }) {
  const [lineId, setLineId] = React.useState(initialLineId)
  const [entries, setEntries] = React.useState([])
  const [userSdwtValues, setUserSdwtValues] = React.useState([])
  const [error, setError] = React.useState(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [hasLoadedOnce, setHasLoadedOnce] = React.useState(false)
  const [lastUpdatedLabel, setLastUpdatedLabel] = React.useState("-")

  const [formValues, setFormValues] = React.useState({ mainStep: "", customEndStep: "" })
  const [formError, setFormError] = React.useState(null)
  const [isCreating, setIsCreating] = React.useState(false)

  const [editingId, setEditingId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState({ mainStep: "", customEndStep: "" })
  const [rowErrors, setRowErrors] = React.useState({})
  const [savingMap, setSavingMap] = React.useState({})

  const hasLoadedRef = React.useRef(false)

  React.useEffect(() => {
    setLineId(initialLineId)
  }, [initialLineId])

  React.useEffect(() => {
    hasLoadedRef.current = false
    setHasLoadedOnce(false)
    setEntries([])
    setError(null)
    setLastUpdatedLabel("-")
    setEditingId(null)
    setRowErrors({})
    setSavingMap({})
    setUserSdwtValues([])
  }, [lineId])

  const fetchEntries = React.useCallback(async () => {
    if (!lineId) {
      setEntries([])
      setUserSdwtValues([])
      setError(null)
      setIsLoading(false)
      setLastUpdatedLabel("-")
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
      return
    }

    setIsLoading(true)
    setError(null)
    if (hasLoadedRef.current) {
      setLastUpdatedLabel("Updating…")
    }

    try {
      const endpoint = buildBackendUrl("/drone-early-inform", { lineId })
      const response = await fetch(endpoint, {
        cache: "no-store",
        credentials: "include",
      })

      let payload = {}
      try {
        payload = await response.json()
      } catch {
        payload = {}
      }

      if (!response.ok) {
        const message =
          payload && typeof payload === "object" && typeof payload.error === "string"
            ? payload.error
            : `Failed to load settings (status ${response.status})`
        throw new Error(message)
      }

      const rows = Array.isArray(payload?.rows) ? payload.rows : []
      const normalized = rows
        .map((row) => normalizeEntry(row, lineId))
        .filter((row) => row !== null)
      const normalizedUsers = normalizeUserSdwt(payload?.userSdwt)

      setEntries(sortEntries(normalized))
      setUserSdwtValues(normalizedUsers)
      setLastUpdatedLabel(timeFormatter.format(new Date()))
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load settings"
      setError(message)
      setUserSdwtValues([])
      if (!hasLoadedRef.current) {
        setLastUpdatedLabel("-")
      }
    } finally {
      setIsLoading(false)
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
    }
  }, [lineId])

  React.useEffect(() => {
    fetchEntries()
  }, [fetchEntries])

  const isRefreshing = isLoading && hasLoadedOnce

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    fetchEntries()
  }, [fetchEntries, lineId])

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const resetForm = React.useCallback(() => {
    setFormValues({ mainStep: "", customEndStep: "" })
    setFormError(null)
  }, [])

  const normalizeDraft = React.useCallback((value) => value.trim(), [])

  const handleCreate = React.useCallback(
    async (event) => {
      event.preventDefault()
      if (!lineId) {
        setFormError("Select a line to add an override")
        return
      }

      const mainStep = normalizeDraft(formValues.mainStep)
      const customEndStep = normalizeDraft(formValues.customEndStep)

      if (!mainStep) {
        setFormError("Main step is required")
        return
      }
      if (mainStep.length > 50) {
        setFormError("Main step must be 50 characters or fewer")
        return
      }
      if (customEndStep.length > 50) {
        setFormError("Custom end step must be 50 characters or fewer")
        return
      }

      setIsCreating(true)
      setFormError(null)

      try {
        const endpoint = buildBackendUrl("/drone-early-inform")
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            lineId,
            mainStep,
            customEndStep: customEndStep.length > 0 ? customEndStep : null,
          }),
        })

        let payload = {}
        try {
          payload = await response.json()
        } catch {
          payload = {}
        }

        if (!response.ok) {
          const apiMessageRaw =
            payload && typeof payload === "object" && typeof payload.error === "string"
              ? payload.error
              : ""
          const apiMessage = unwrapErrorMessage(apiMessageRaw)
          const lowerApiMessage = apiMessage.toLowerCase()
          const isDuplicate =
            response.status === 409 ||
            lowerApiMessage.includes("already") ||
            lowerApiMessage.includes("duplicate") ||
            lowerApiMessage.includes("uniq") ||
            lowerApiMessage.includes("main step")
          const message = isDuplicate
            ? "이미 등록된 스텝입니다."
            : apiMessage || `Failed to create entry (status ${response.status})`
          throw new Error(message)
        }

        const entry = normalizeEntry(payload?.entry, lineId)
        if (entry) {
          setEntries((prev) => sortEntries([...prev.filter((item) => item.id !== entry.id), entry]))
          setLastUpdatedLabel(timeFormatter.format(new Date()))
        }
        resetForm()
        showCreateToast()
      } catch (requestError) {
        const rawMessage =
          requestError instanceof Error ? requestError.message : "Failed to create entry"
        const lower = rawMessage.toLowerCase()
        const isDuplicate =
          lower.includes("already") ||
          lower.includes("duplicate") ||
          lower.includes("uniq") ||
          lower.includes("main step")
        const friendlyMessage = isDuplicate
          ? "이미 등록된 스텝입니다. 다른 스텝을 입력해주세요."
          : rawMessage
        setFormError(friendlyMessage)
        showRequestErrorToast(friendlyMessage)
      } finally {
        setIsCreating(false)
      }
    },
    [formValues, lineId, normalizeDraft, resetForm]
  )

  const startEditing = React.useCallback((entry) => {
    setEditingId(entry.id)
    setEditDraft({ mainStep: entry.mainStep, customEndStep: entry.customEndStep ?? "" })
    setRowErrors((prev) => {
      if (!(entry.id in prev)) return prev
      const next = { ...prev }
      delete next[entry.id]
      return next
    })
  }, [])

  const cancelEditing = React.useCallback(() => {
    setEditingId(null)
    setEditDraft({ mainStep: "", customEndStep: "" })
  }, [])

  const handleEditChange = React.useCallback((key, value) => {
    setEditDraft((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = React.useCallback(async () => {
    if (!editingId) return
    const entry = entries.find((item) => item.id === editingId)
    if (!entry) {
      cancelEditing()
      return
    }

    const nextMainStep = normalizeDraft(editDraft.mainStep)
    const nextCustom = normalizeDraft(editDraft.customEndStep ?? "")
    const updates = {}

    if (!nextMainStep) {
      setRowErrors((prev) => ({ ...prev, [entry.id]: "Main step is required" }))
      return
    }
    if (nextMainStep.length > 50) {
      setRowErrors((prev) => ({ ...prev, [entry.id]: "Main step must be 50 characters or fewer" }))
      return
    }
    if (nextCustom.length > 50) {
      setRowErrors((prev) => ({ ...prev, [entry.id]: "Custom end step must be 50 characters or fewer" }))
      return
    }

    if (nextMainStep !== entry.mainStep) {
      updates.mainStep = nextMainStep
    }

    const normalizedOriginal = (entry.customEndStep ?? "").trim()
    if (nextCustom !== normalizedOriginal) {
      updates.customEndStep = nextCustom.length > 0 ? nextCustom : null
    }

    if (Object.keys(updates).length === 0) {
      cancelEditing()
      return
    }

    setSavingMap((prev) => ({ ...prev, [entry.id]: true }))
    setRowErrors((prev) => {
      if (!(entry.id in prev)) return prev
      const next = { ...prev }
      delete next[entry.id]
      return next
    })

    try {
      const endpoint = buildBackendUrl("/drone-early-inform")
      const response = await fetch(endpoint, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          id: Number.parseInt(entry.id, 10),
          ...updates,
        }),
      })

      let payload = {}
      try {
        payload = await response.json()
      } catch {
        payload = {}
      }

      if (!response.ok) {
        const message =
          payload && typeof payload === "object" && typeof payload.error === "string"
            ? payload.error
            : `Failed to update entry (status ${response.status})`
        throw new Error(message)
      }

      const updated = normalizeEntry(payload?.entry, entry.lineId)
      if (updated) {
        setEntries((prev) =>
          sortEntries(prev.map((item) => (item.id === entry.id ? updated : item)))
        )
        setLastUpdatedLabel(timeFormatter.format(new Date()))
      }
      showUpdateToast()
      cancelEditing()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update entry"
      setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
      showRequestErrorToast(message)
    } finally {
      setSavingMap((prev) => {
        if (!(entry.id in prev)) return prev
        const next = { ...prev }
        delete next[entry.id]
        return next
      })
    }
  }, [cancelEditing, editDraft, editingId, entries, normalizeDraft])

  const handleDelete = React.useCallback(
    async (entry) => {
      if (!entry) return
      const confirmed = window.confirm(
        `Delete override for main step "${entry.mainStep}"? This action cannot be undone.`
      )
      if (!confirmed) return

      setSavingMap((prev) => ({ ...prev, [entry.id]: true }))
      setRowErrors((prev) => {
        if (!(entry.id in prev)) return prev
        const next = { ...prev }
        delete next[entry.id]
        return next
      })

      try {
        const endpoint = buildBackendUrl("/drone-early-inform", { id: entry.id })
        const response = await fetch(endpoint, {
          method: "DELETE",
          credentials: "include",
        })

        let payload = {}
        try {
          payload = await response.json()
        } catch {
          payload = {}
        }

        if (!response.ok) {
          const message =
            payload && typeof payload === "object" && typeof payload.error === "string"
              ? payload.error
              : `Failed to delete entry (status ${response.status})`
          throw new Error(message)
        }

        setEntries((prev) => prev.filter((item) => item.id !== entry.id))
        if (editingId === entry.id) {
          cancelEditing()
        }
        setLastUpdatedLabel(timeFormatter.format(new Date()))
        showDeleteToast()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to delete entry"
        setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
        showRequestErrorToast(message)
      } finally {
        setSavingMap((prev) => {
          if (!(entry.id in prev)) return prev
          const next = { ...prev }
          delete next[entry.id]
          return next
        })
      }
    },
    [cancelEditing, editingId]
  )

  return (
    <section className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <IconSettings className="size-5" />
            {lineId ? `${lineId} ${LABELS.titleSuffix}` : LABELS.titleSuffix}
            <div className="ml-2 self-end text-[10px] font-normal text-muted-foreground" aria-live="polite">
              {LABELS.updated} {lastUpdatedLabel}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={!lineId || isRefreshing}
            className="gap-1"
            aria-label={LABELS.refresh}
            title={LABELS.refresh}
          >
            <IconRefresh className={`size-3 ${isRefreshing ? "animate-spin" : ""}`} />
            {LABELS.refresh}
          </Button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="rounded-lg border bg-background px-4 py-2 shadow-sm">

        <div className="flex flex-col gap-1 pb-4">
          <h2 className="text-md font-medium">{LABELS.addTitle}</h2>
          <p className="text-xs text-muted-foreground">{LABELS.addDescription}</p>
        </div>

        {formError ? (
          <p className="text-xs text-destructive" role="alert">
            {formError}
          </p>) :
          (<p className="text-xs">&nbsp;</p>)

        }

        <div className="flex justify-between items-end flex-wrap mb-2">
          <form className="flex flex-row items-center gap-3 flex-wrap" onSubmit={handleCreate}>
            <div className="w-80 space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="main-step-input">
                {LABELS.mainStep}
              </label>
              <Input
                id="main-step-input"
                value={formValues.mainStep}
                onChange={(event) => handleFormChange("mainStep", event.target.value)}
                placeholder="ex) STEP_10"
                required
                maxLength={50}
              />
            </div>

            <div className="w-80 space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="custom-step-input">
                {LABELS.customEndStep}
              </label>
              <Input
                id="custom-step-input"
                value={formValues.customEndStep}
                onChange={(event) => handleFormChange("customEndStep", event.target.value)}
                placeholder="조기 알람 받을 스텝"
                maxLength={50}
              />
            </div>

            <Button
              type="submit"
              className="md:self-end"
              disabled={isCreating || !lineId}
            >
              <IconPlus className="mr-1 size-4" />
              {LABELS.addButton}
            </Button>
          </form>

          <div className="pt-2">
            <LineUserSdwtBadges lineId={lineId} values={userSdwtValues} />
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 rounded-lg border bg-background">
        <TableContainer className="max-h-full overflow-auto">
          <Table stickyHeader className="w-full table-fixed">
            {/* ✅ colgroup으로 컬럼 폭을 한 번에 관리 */}
            <colgroup>
              <col className="w-30" />  {/* Line ID */}
              <col className="w-40" />  {/* Main Step */}
              <col className="w-40" />  {/* Custom End Step */}
              <col className="w-32" />  {/* Updated By */}
              <col className="w-40" />  {/* Updated At */}
              <col className="w-60" />  {/* Actions */}
            </colgroup>

            <TableHeader className="sticky top-0 z-10 bg-muted">
              <TableRow>
                <TableHead className="text-center">{LABELS.lineId}</TableHead>
                <TableHead className="text-center">{LABELS.mainStep}</TableHead>
                <TableHead className="text-center">{LABELS.customEndStep}</TableHead>
                <TableHead className="text-center">{LABELS.updatedBy}</TableHead>
                <TableHead className="text-center">{LABELS.updatedAt}</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {isLoading && !hasLoadedOnce && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-24 text-center text-sm text-muted-foreground"
                  >
                    {LABELS.loading}
                  </TableCell>
                </TableRow>
              )}

              {!isLoading && entries.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-24 text-center text-sm text-muted-foreground"
                  >
                    {lineId ? LABELS.empty : "Select a line to view overrides."}
                  </TableCell>
                </TableRow>
              )}

              {entries.map((entry) => {
                const isEditing = editingId === entry.id
                const isSaving = Boolean(savingMap[entry.id])
                const rowError = rowErrors[entry.id]

                return (
                  <React.Fragment key={entry.id}>
                    <TableRow>
                      <TableCell className="text-center font-mono text-xs text-muted-foreground">
                        {entry.lineId || "-"}
                      </TableCell>

                      {/* ✅ Main Step 가운데 정렬 */}
                      <TableCell className="text-center">
                        {isEditing ? (
                          <Input
                            value={editDraft.mainStep}
                            onChange={(event) =>
                              handleEditChange("mainStep", event.target.value)
                            }
                            maxLength={50}
                            disabled={isSaving}
                            className="text-center"
                          />
                        ) : (
                          <span className="font-medium">{entry.mainStep}</span>
                        )}
                      </TableCell>

                      {/* ✅ Custom End Step 가운데 정렬 */}
                      <TableCell className="text-center">
                        {isEditing ? (
                          <Input
                            value={editDraft.customEndStep ?? ""}
                            onChange={(event) =>
                              handleEditChange("customEndStep", event.target.value)
                            }
                            maxLength={50}
                            disabled={isSaving}
                            className="text-center"
                          />
                        ) : entry.customEndStep && entry.customEndStep.trim().length > 0 ? (
                          entry.customEndStep
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>

                      <TableCell className="text-center text-xs text-muted-foreground">
                        {entry.updatedBy || "-"}
                      </TableCell>

                      <TableCell className="text-center text-xs text-muted-foreground">
                        {formatUpdatedAt(entry.updatedAt)}
                      </TableCell>

                      {/* ✅ Actions도 가운데 정렬 */}
                      <TableCell className="text-end">
                        <div className="inline-flex items-center justify-end gap-2">
                          {isEditing ? (
                            <>
                              <Button
                                size="sm"
                                onClick={handleSave}
                                disabled={isSaving}
                                className="gap-1"
                              >
                                <IconDeviceFloppy className="size-4" />
                                Save
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={cancelEditing}
                                disabled={isSaving}
                                className="gap-1"
                              >
                                <IconX className="size-4" />
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => startEditing(entry)}
                                className="gap-1"
                              >
                                <IconPencil className="size-4" />
                                Edit
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDelete(entry)}
                                className="gap-1 text-destructive"
                              >
                                <IconTrash className="size-4" />
                                Delete
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {rowError && (
                      <TableRow>
                        <TableCell
                          colSpan={6}
                          className="bg-destructive/5 px-4 py-2 text-xs text-destructive text-center"
                        >
                          {rowError}
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </div>

    </section >
  )
}
