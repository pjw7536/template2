// src/features/line-dashboard/hooks/useLineSettings.js
// 라인 조기 알림 설정 데이터를 관리하는 전용 훅
import * as React from "react"

import {
  createLineSetting,
  deleteLineSetting,
  fetchLineSettings,
  updateLineSetting,
} from "../api"
import { timeFormatter } from "../utils/formatters"
import { sortEntries } from "../utils/line-settings"

export function useLineSettings(lineId) {
  const [entries, setEntries] = React.useState([])
  const [userSdwtValues, setUserSdwtValues] = React.useState([])
  const [error, setError] = React.useState(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [hasLoadedOnce, setHasLoadedOnce] = React.useState(false)
  const [lastUpdatedLabel, setLastUpdatedLabel] = React.useState("-")

  const hasLoadedRef = React.useRef(false)

  React.useEffect(() => {
    setEntries([])
    setUserSdwtValues([])
    setError(null)
    setLastUpdatedLabel("-")
    setHasLoadedOnce(false)
    hasLoadedRef.current = false
  }, [lineId])

  const refresh = React.useCallback(async () => {
    if (!lineId) {
      setEntries([])
      setUserSdwtValues([])
      setError(null)
      setLastUpdatedLabel("-")
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
      return { ok: true }
    }

    setIsLoading(true)
    setError(null)
    if (hasLoadedRef.current) {
      setLastUpdatedLabel("Updating…")
    }

    try {
      const { entries: loadedEntries, userSdwtValues: loadedUsers } = await fetchLineSettings(lineId)
      setEntries(sortEntries(loadedEntries || []))
      setUserSdwtValues(loadedUsers || [])
      setLastUpdatedLabel(timeFormatter.format(new Date()))
      return { ok: true }
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load settings"
      setError(message)
      setUserSdwtValues([])
      if (!hasLoadedRef.current) {
        setLastUpdatedLabel("-")
      }
      return { ok: false, error: requestError }
    } finally {
      setIsLoading(false)
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
    }
  }, [lineId])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  const createEntry = React.useCallback(
    async ({ mainStep, customEndStep }) => {
      const { entry } = await createLineSetting({ lineId, mainStep, customEndStep })
      if (entry) {
        setEntries((prev) => sortEntries([...prev.filter((item) => item.id !== entry.id), entry]))
        setLastUpdatedLabel(timeFormatter.format(new Date()))
      }
      return entry
    },
    [lineId],
  )

  const updateEntry = React.useCallback(
    async ({ id, mainStep, customEndStep }) => {
      const { entry } = await updateLineSetting({ id, lineId, mainStep, customEndStep })
      if (entry) {
        setEntries((prev) =>
          sortEntries(prev.map((item) => (item.id === entry.id ? entry : item))),
        )
        setLastUpdatedLabel(timeFormatter.format(new Date()))
      }
      return entry
    },
    [lineId],
  )

  const deleteEntry = React.useCallback(async ({ id }) => {
    await deleteLineSetting({ id })
    setEntries((prev) => prev.filter((item) => item.id !== String(id)))
    setLastUpdatedLabel(timeFormatter.format(new Date()))
    return { ok: true }
  }, [])

  return {
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
  }
}
