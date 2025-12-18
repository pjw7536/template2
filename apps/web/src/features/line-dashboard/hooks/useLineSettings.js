// src/features/line-dashboard/hooks/useLineSettings.js
// 라인 조기 알림 설정 데이터를 관리하는 전용 훅 (비동기 로딩 + CRUD 포함)
import * as React from "react"

import {
  createLineSetting,
  deleteLineSetting,
  fetchLineSettings,
  updateLineSetting,
} from "../api"
import { timeFormatter } from "../utils/formatters"
import { sortEntries } from "../utils/line-settings"

const EMPTY_TIMESTAMP = "-"

const normalizeId = (value) => String(value ?? "")
const nowLabel = () => timeFormatter.format(new Date())

export function useLineSettings(lineId) {
  const [entries, setEntries] = React.useState([])
  const [userSdwtValues, setUserSdwtValues] = React.useState([])
  const [error, setError] = React.useState(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [hasLoadedOnce, setHasLoadedOnce] = React.useState(false)
  const [lastUpdatedLabel, setLastUpdatedLabel] = React.useState(EMPTY_TIMESTAMP)

  const hasLoadedRef = React.useRef(false)

  const resetForLineChange = React.useCallback(() => {
    setEntries([])
    setUserSdwtValues([])
    setError(null)
    setLastUpdatedLabel(EMPTY_TIMESTAMP)
    setHasLoadedOnce(false)
    hasLoadedRef.current = false
  }, [])

  React.useEffect(() => {
    resetForLineChange()
  }, [lineId, resetForLineChange])

  const refresh = React.useCallback(async () => {
    // 라인을 선택하지 않은 경우: 네트워크 호출을 생략하고 초기 상태만 반환
    if (!lineId) {
      resetForLineChange()
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
      setLastUpdatedLabel(nowLabel())
      return { ok: true }
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Failed to load settings"
      setError(message)
      setUserSdwtValues([])
      if (!hasLoadedRef.current) {
        setLastUpdatedLabel(EMPTY_TIMESTAMP)
      }
      return { ok: false, error: requestError }
    } finally {
      setIsLoading(false)
      if (!hasLoadedRef.current) {
        hasLoadedRef.current = true
        setHasLoadedOnce(true)
      }
    }
  }, [lineId, resetForLineChange])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  const createEntry = React.useCallback(
    async ({ mainStep, customEndStep }) => {
      const { entry } = await createLineSetting({ lineId, mainStep, customEndStep })
      if (entry) {
        setEntries((prev) =>
          sortEntries([...prev.filter((item) => item.id !== entry.id), entry]),
        )
        setLastUpdatedLabel(nowLabel())
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
        setLastUpdatedLabel(nowLabel())
      }
      return entry
    },
    [lineId],
  )

  const deleteEntry = React.useCallback(async ({ id }) => {
    await deleteLineSetting({ id })
    const normalizedId = normalizeId(id)
    setEntries((prev) => prev.filter((item) => normalizeId(item.id) !== normalizedId))
    setLastUpdatedLabel(nowLabel())
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
