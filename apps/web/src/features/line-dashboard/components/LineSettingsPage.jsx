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
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useLineSettings } from "../hooks"
import { buildToastOptions } from "./data-table/utils/toast"
import {
  formatUpdatedAt,
  isDuplicateMessage,
  normalizeDraft,
} from "../utils/line-settings"

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

const SUCCESS_COLOR = "var(--chart-2)"
const INFO_COLOR = "var(--chart-3)"
const ERROR_COLOR = "var(--destructive)"
const DUPLICATE_MESSAGE = "이미 등록된 스텝입니다. 다른 스텝을 입력해주세요."

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

export function LineSettingsPage({ lineId = "" }) {
  const {
    entries,
    userSdwtValues,
    error,
    isLoading,
    hasLoadedOnce,
    lastUpdatedLabel,
    refresh,
    createEntry,
    updateEntry,
    deleteEntry,
  } = useLineSettings(lineId)

  const [formValues, setFormValues] = React.useState({ mainStep: "", customEndStep: "" })
  const [formError, setFormError] = React.useState(null)
  const [isCreating, setIsCreating] = React.useState(false)

  const [editingId, setEditingId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState({ mainStep: "", customEndStep: "" })
  const [rowErrors, setRowErrors] = React.useState({})
  const [savingMap, setSavingMap] = React.useState({})

  const isRefreshing = isLoading && hasLoadedOnce

  const handleRefresh = React.useCallback(() => {
    if (!lineId) return
    refresh()
  }, [lineId, refresh])

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const resetForm = React.useCallback(() => {
    setFormValues({ mainStep: "", customEndStep: "" })
    setFormError(null)
  }, [])

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
        const entry = await createEntry({
          mainStep,
          customEndStep: customEndStep.length > 0 ? customEndStep : null,
        })
        if (entry) {
          resetForm()
          showCreateToast()
        }
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to create entry"
        const friendlyMessage =
          requestError?.status === 409 || isDuplicateMessage(message)
            ? DUPLICATE_MESSAGE
            : message
        setFormError(friendlyMessage)
        showRequestErrorToast(friendlyMessage)
      } finally {
        setIsCreating(false)
      }
    },
    [createEntry, formValues.customEndStep, formValues.mainStep, lineId, resetForm],
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
      setRowErrors((prev) => ({
        ...prev,
        [entry.id]: "Custom end step must be 50 characters or fewer",
      }))
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
      await updateEntry({ id: entry.id, ...updates })
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
  }, [cancelEditing, editDraft.customEndStep, editDraft.mainStep, editingId, entries, updateEntry])

  const handleDelete = React.useCallback(
    async (entry) => {
      if (!entry) return
      const confirmed = window.confirm(
        `Delete override for main step "${entry.mainStep}"? This action cannot be undone.`,
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
        await deleteEntry({ id: entry.id })
        if (editingId === entry.id) {
          cancelEditing()
        }
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
    [cancelEditing, deleteEntry, editingId],
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
          </p>
        ) : (
          <p className="text-xs">&nbsp;</p>
        )}

        <div className="mb-2 flex flex-wrap items-end justify-between">
          <form className="flex flex-row flex-wrap items-center gap-3" onSubmit={handleCreate}>
            <div className="w-80 space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="main-step-input">
                {LABELS.mainStep}
              </label>
              <Input
                id="main-step-input"
                value={formValues.mainStep}
                onChange={(event) => handleFormChange("mainStep", event.target.value)}
                placeholder="ex) AB123456"
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

            <Button type="submit" className="md:self-end" disabled={isCreating || !lineId}>
              <IconPlus className="mr-1 size-4" />
              {LABELS.addButton}
            </Button>
          </form>

          <div className="pt-2">
            <LineUserSdwtBadges lineId={lineId} values={userSdwtValues} />
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 rounded-lg border bg-background">
        <TableContainer className="max-h-full overflow-auto">
          <Table stickyHeader className="w-full table-fixed">
            <colgroup>
              <col className="w-30" />
              <col className="w-40" />
              <col className="w-40" />
              <col className="w-32" />
              <col className="w-40" />
              <col className="w-60" />
            </colgroup>

            <TableHeader className="sticky top-0 z-10 bg-muted">
              <TableRow>
                <TableHead className="text-center">{LABELS.lineId}</TableHead>
                <TableHead className="text-center">{LABELS.mainStep}</TableHead>
                <TableHead className="text-center">{LABELS.customEndStep}</TableHead>
                <TableHead className="text-center">{LABELS.updatedBy}</TableHead>
                <TableHead className="text-center">{LABELS.updatedAt}</TableHead>
                <TableHead className="text-right" />
              </TableRow>
            </TableHeader>

            <TableBody>
              {isLoading && !hasLoadedOnce && (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-sm text-muted-foreground">
                    {LABELS.loading}
                  </TableCell>
                </TableRow>
              )}

              {!isLoading && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-sm text-muted-foreground">
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

                      <TableCell className="text-center">
                        {isEditing ? (
                          <Input
                            value={editDraft.mainStep}
                            onChange={(event) => handleEditChange("mainStep", event.target.value)}
                            maxLength={50}
                            disabled={isSaving}
                            className="text-center"
                          />
                        ) : (
                          <span className="font-medium">{entry.mainStep}</span>
                        )}
                      </TableCell>

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

                      <TableCell className="text-end">
                        <div className="inline-flex items-center justify-end gap-2">
                          {isEditing ? (
                            <>
                              <Button size="sm" onClick={handleSave} disabled={isSaving} className="gap-1">
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
                          className="bg-destructive/5 px-4 py-2 text-center text-xs text-destructive"
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
    </section>
  )
}
