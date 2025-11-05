// src/features/line-dashboard/components/LineSettingsPage.jsx
"use client"

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

import { Button } from "@/components/ui/button"
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

const LABELS = {
  titleSuffix: "Line E-SOP Settings",
  subtitle: "Manage custom end step overrides for drone_early_inform_v3.",
  addTitle: "Add override",
  addDescription: "Leave Custom End Step empty to clear any override.",
  mainStep: "Main Step",
  customEndStep: "Custom End Step",
  addButton: "Add",
  refresh: "Refresh",
  updated: "Updated",
  loading: "Loading entries…",
  empty: "No overrides found for this line.",
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

  return {
    id: String(rawId),
    lineId,
    mainStep: mainStepRaw,
    customEndStep,
  }
}

function sortEntries(entries) {
  return [...entries].sort((a, b) =>
    a.mainStep.localeCompare(b.mainStep, undefined, { numeric: true, sensitivity: "base" })
  )
}

export function LineSettingsPage({ lineId: initialLineId = "" }) {
  const [lineId, setLineId] = React.useState(initialLineId)
  const [entries, setEntries] = React.useState([])
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
  }, [lineId])

  const fetchEntries = React.useCallback(async () => {
    if (!lineId) {
      setEntries([])
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

      setEntries(sortEntries(normalized))
      setLastUpdatedLabel(timeFormatter.format(new Date()))
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load settings"
      setError(message)
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
          const message =
            payload && typeof payload === "object" && typeof payload.error === "string"
              ? payload.error
              : `Failed to create entry (status ${response.status})`
          throw new Error(message)
        }

        const entry = normalizeEntry(payload?.entry, lineId)
        if (entry) {
          setEntries((prev) => sortEntries([...prev.filter((item) => item.id !== entry.id), entry]))
          setLastUpdatedLabel(timeFormatter.format(new Date()))
        }
        resetForm()
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to create entry"
        setFormError(message)
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
      cancelEditing()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to update entry"
      setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
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
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "Failed to delete entry"
        setRowErrors((prev) => ({ ...prev, [entry.id]: message }))
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
    <section className="flex h-full min-h-0 flex-col gap-4 px-4 pb-6 pt-4 lg:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <IconSettings className="size-5" />
            {lineId ? `${lineId} ${LABELS.titleSuffix}` : LABELS.titleSuffix}
            <span className="ml-2 text-[10px] font-normal text-muted-foreground" aria-live="polite">
              {LABELS.updated} {lastUpdatedLabel}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{LABELS.subtitle}</p>
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

      <div className="rounded-lg border bg-background p-4 shadow-sm">
        <div className="flex flex-col gap-1 pb-3">
          <h2 className="text-sm font-medium">{LABELS.addTitle}</h2>
          <p className="text-xs text-muted-foreground">{LABELS.addDescription}</p>
        </div>

        <form className="flex flex-col gap-3 md:flex-row md:items-end" onSubmit={handleCreate}>
          <div className="flex-1 space-y-1">
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

          <div className="flex-1 space-y-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="custom-step-input">
              {LABELS.customEndStep}
            </label>
            <Input
              id="custom-step-input"
              value={formValues.customEndStep}
              onChange={(event) => handleFormChange("customEndStep", event.target.value)}
              placeholder="Leave blank to remove override"
              maxLength={50}
            />
          </div>

          <Button
            type="submit"
            className="md:self-start"
            disabled={isCreating || !lineId}
          >
            <IconPlus className="mr-1 size-4" />
            {LABELS.addButton}
          </Button>
        </form>

        {formError && (
          <p className="pt-2 text-xs text-destructive" role="alert">
            {formError}
          </p>
        )}
      </div>

      <div className="flex-1 min-h-0 rounded-lg border bg-background">
        <TableContainer className="max-h-full overflow-auto">
          <Table stickyHeader>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">ID</TableHead>
                <TableHead>{LABELS.mainStep}</TableHead>
                <TableHead>{LABELS.customEndStep}</TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !hasLoadedOnce && (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-sm text-muted-foreground">
                    {LABELS.loading}
                  </TableCell>
                </TableRow>
              )}

              {!isLoading && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-sm text-muted-foreground">
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
                      <TableCell className="font-mono text-xs text-muted-foreground">{entry.id}</TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            value={editDraft.mainStep}
                            onChange={(event) => handleEditChange("mainStep", event.target.value)}
                            maxLength={50}
                            disabled={isSaving}
                          />
                        ) : (
                          <span className="font-medium">{entry.mainStep}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isEditing ? (
                          <Input
                            value={editDraft.customEndStep ?? ""}
                            onChange={(event) => handleEditChange("customEndStep", event.target.value)}
                            maxLength={50}
                            disabled={isSaving}
                          />
                        ) : entry.customEndStep && entry.customEndStep.trim().length > 0 ? (
                          entry.customEndStep
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-2">
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
                        <TableCell colSpan={4} className="bg-destructive/5 px-4 py-2 text-xs text-destructive">
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
