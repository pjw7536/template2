import * as React from "react"

import { isDuplicateMessage } from "../utils/lineSettings"
import { DUPLICATE_MESSAGE } from "../utils/lineSettingsConfig"
import {
  showCreateToast,
  showDeleteToast,
  showRequestErrorToast,
  showUpdateToast,
} from "../utils/lineSettingsToasts"
import { validateStepDraft } from "../utils/lineSettingsValidation"

const EMPTY_STEP_DRAFT = { mainStep: "", customEndStep: "" }

export function useEarlyInformSettingsController({
  lineId,
  entries,
  createEntry,
  updateEntry,
  deleteEntry,
}) {
  const [formValues, setFormValues] = React.useState(EMPTY_STEP_DRAFT)
  const [formError, setFormError] = React.useState(null)
  const [isCreating, setIsCreating] = React.useState(false)
  const [editingId, setEditingId] = React.useState(null)
  const [editDraft, setEditDraft] = React.useState(EMPTY_STEP_DRAFT)
  const [rowErrors, setRowErrors] = React.useState({})
  const [savingMap, setSavingMap] = React.useState({})

  const handleFormChange = React.useCallback((key, value) => {
    setFormValues((previous) => ({ ...previous, [key]: value }))
  }, [])

  const resetForm = React.useCallback(() => {
    setFormValues(EMPTY_STEP_DRAFT)
    setFormError(null)
  }, [])

  const handleCreate = React.useCallback(async (event) => {
    event.preventDefault()
    if (!lineId) {
      setFormError("Select a line to add an override")
      return
    }

    const { normalizedMainStep, normalizedCustom, error: draftError } = validateStepDraft({
      mainStep: formValues.mainStep,
      customEndStep: formValues.customEndStep,
    })
    if (draftError) {
      setFormError(draftError)
      return
    }

    setIsCreating(true)
    setFormError(null)
    try {
      const entry = await createEntry({
        mainStep: normalizedMainStep,
        customEndStep: normalizedCustom.length > 0 ? normalizedCustom : null,
      })
      if (entry) {
        resetForm()
        showCreateToast()
      }
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Failed to create entry"
      const friendlyMessage = requestError?.status === 409 || isDuplicateMessage(message)
        ? DUPLICATE_MESSAGE
        : message
      setFormError(friendlyMessage)
      showRequestErrorToast(friendlyMessage)
    } finally {
      setIsCreating(false)
    }
  }, [createEntry, formValues.customEndStep, formValues.mainStep, lineId, resetForm])

  const startEditing = React.useCallback((entry) => {
    setEditingId(entry.id)
    setEditDraft({ mainStep: entry.mainStep, customEndStep: entry.customEndStep ?? "" })
    setRowErrors((previous) => {
      if (!(entry.id in previous)) return previous
      const next = { ...previous }
      delete next[entry.id]
      return next
    })
  }, [])

  const cancelEditing = React.useCallback(() => {
    setEditingId(null)
    setEditDraft(EMPTY_STEP_DRAFT)
  }, [])

  const handleEditChange = React.useCallback((key, value) => {
    setEditDraft((previous) => ({ ...previous, [key]: value }))
  }, [])

  const handleSave = React.useCallback(async () => {
    if (!editingId) return
    const entry = entries.find((item) => item.id === editingId)
    if (!entry) {
      cancelEditing()
      return
    }

    const { normalizedMainStep, normalizedCustom, error: draftError } = validateStepDraft({
      mainStep: editDraft.mainStep,
      customEndStep: editDraft.customEndStep,
    })
    const updates = {}

    if (draftError) {
      setRowErrors((previous) => ({ ...previous, [entry.id]: draftError }))
      return
    }
    if (normalizedMainStep !== entry.mainStep) {
      updates.mainStep = normalizedMainStep
    }

    const normalizedOriginal = (entry.customEndStep ?? "").trim()
    if (normalizedCustom !== normalizedOriginal) {
      updates.customEndStep = normalizedCustom.length > 0 ? normalizedCustom : null
    }
    if (Object.keys(updates).length === 0) {
      cancelEditing()
      return
    }

    setSavingMap((previous) => ({ ...previous, [entry.id]: true }))
    setRowErrors((previous) => {
      if (!(entry.id in previous)) return previous
      const next = { ...previous }
      delete next[entry.id]
      return next
    })

    try {
      await updateEntry({ id: entry.id, ...updates })
      showUpdateToast()
      cancelEditing()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Failed to update entry"
      setRowErrors((previous) => ({ ...previous, [entry.id]: message }))
      showRequestErrorToast(message)
    } finally {
      setSavingMap((previous) => {
        if (!(entry.id in previous)) return previous
        const next = { ...previous }
        delete next[entry.id]
        return next
      })
    }
  }, [cancelEditing, editDraft.customEndStep, editDraft.mainStep, editingId, entries, updateEntry])

  const handleDelete = React.useCallback(async (entry) => {
    if (!entry) return
    const confirmed = window.confirm(
      `Delete override for main step "${entry.mainStep}"? This action cannot be undone.`,
    )
    if (!confirmed) return

    setSavingMap((previous) => ({ ...previous, [entry.id]: true }))
    setRowErrors((previous) => {
      if (!(entry.id in previous)) return previous
      const next = { ...previous }
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
      const message = requestError instanceof Error ? requestError.message : "Failed to delete entry"
      setRowErrors((previous) => ({ ...previous, [entry.id]: message }))
      showRequestErrorToast(message)
    } finally {
      setSavingMap((previous) => {
        if (!(entry.id in previous)) return previous
        const next = { ...previous }
        delete next[entry.id]
        return next
      })
    }
  }, [cancelEditing, deleteEntry, editingId])

  return {
    formValues,
    formError,
    isCreating,
    editingId,
    editDraft,
    rowErrors,
    savingMap,
    handleFormChange,
    handleCreate,
    startEditing,
    cancelEditing,
    handleEditChange,
    handleSave,
    handleDelete,
  }
}
