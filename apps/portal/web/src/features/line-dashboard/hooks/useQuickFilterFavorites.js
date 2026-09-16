// src/features/line-dashboard/hooks/useQuickFilterFavorites.js
import * as React from "react"

import {
  createInitialQuickFilters,
  syncQuickFiltersToSections,
} from "../utils/dataTableQuickFilters"

const STORAGE_KEY_PREFIX = "line-dashboard:quick-filter-favorites"
const DEFAULT_OWNER = "anonymous"
const DEFAULT_LINE = "__default-line__"

const hasWindow = typeof window !== "undefined"

function makeStorageKey(ownerId) {
  const safeOwner = ownerId ? String(ownerId).trim().toLowerCase() : DEFAULT_OWNER
  return `${STORAGE_KEY_PREFIX}:${safeOwner}`
}

function normalizeLineId(lineId) {
  const raw = lineId == null ? "" : String(lineId).trim()
  return raw ? raw.toLowerCase() : DEFAULT_LINE
}

function sanitizeFilters(rawFilters, sections) {
  if (!Array.isArray(sections) || sections.length === 0) {
    // 섹션 정보가 없으면 있는 그대로 둡니다. 이후 섹션 준비 후 sync.
    return rawFilters ?? {}
  }
  const base = createInitialQuickFilters()
  const merged = { ...base, ...(rawFilters ?? {}) }
  return syncQuickFiltersToSections(merged, sections, { preserveMissing: true })
}

function loadFavorites(storageKey, sections, defaultLineId) {
  if (!hasWindow) return []
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((entry) => {
        if (!entry || typeof entry !== "object") return null
        const name = typeof entry.name === "string" ? entry.name.trim() : ""
        const id = typeof entry.id === "string" ? entry.id : null
        if (!name || !id) return null
        return {
          id,
          name,
          lineId: normalizeLineId(entry.lineId ?? defaultLineId),
          filters: sanitizeFilters(entry.filters, sections),
        }
      })
      .filter(Boolean)
  } catch (error) {
    console.error("Failed to load quick filter favorites", error)
    return []
  }
}

function persistFavorites(storageKey, favorites) {
  if (!hasWindow) return
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(favorites))
  } catch (error) {
    console.error("Failed to save quick filter favorites", error)
  }
}

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function useQuickFilterFavorites({
  filters,
  sections,
  replaceFilters,
  ownerId,
  lineId,
}) {
  const storageKey = React.useMemo(() => makeStorageKey(ownerId), [ownerId])
  const normalizedLineId = React.useMemo(() => normalizeLineId(lineId), [lineId])

  const [favorites, setFavorites] = React.useState(() =>
    loadFavorites(storageKey, sections, normalizedLineId)
  )

  React.useEffect(() => {
    setFavorites(loadFavorites(storageKey, sections, normalizedLineId))
  }, [storageKey, sections, normalizedLineId])

  React.useEffect(() => {
    setFavorites((previous) => {
      const shouldSanitize = Array.isArray(sections) && sections.length > 0
      if (!shouldSanitize) return previous
      return previous.map((favorite) => ({
        ...favorite,
        lineId: normalizeLineId(favorite.lineId ?? normalizedLineId),
        filters: sanitizeFilters(favorite.filters, sections),
      }))
    })
  }, [sections, normalizedLineId])

  React.useEffect(() => {
    persistFavorites(storageKey, favorites)
  }, [favorites, storageKey])

  const favoritesByLine = React.useMemo(
    () => favorites.filter((favorite) => favorite.lineId === normalizedLineId),
    [favorites, normalizedLineId]
  )

  const saveFavorite = React.useCallback(
    (name) => {
      const trimmed = typeof name === "string" ? name.trim() : ""
      if (!trimmed) return
      const sanitizedFilters = sanitizeFilters(filters, sections)

      let createdId = null

      setFavorites((previous) => {
        const normalizedName = trimmed.toLowerCase()
        const hasDuplicateInLine = previous.some(
          (favorite) =>
            favorite.lineId === normalizedLineId &&
            favorite.name.toLowerCase() === normalizedName
        )

        if (hasDuplicateInLine) {
          return previous
        }

        const nextFavorite = {
          id: createId(),
          name: trimmed,
          lineId: normalizedLineId,
          filters: sanitizedFilters,
        }

        createdId = nextFavorite.id

        return [...previous, nextFavorite]
      })

      return createdId
    },
    [filters, sections, normalizedLineId]
  )

  const updateFavorite = React.useCallback(
    (id, name) => {
      if (!id) return null
      const trimmed = typeof name === "string" ? name.trim() : ""
      if (!trimmed) return null
      const sanitizedFilters = sanitizeFilters(filters, sections)

      setFavorites((previous) => {
        const target = previous.find((favorite) => favorite.id === id)
        if (!target) return previous
        const updated = {
          ...target,
          name: trimmed,
          filters: sanitizedFilters,
          lineId: target.lineId ?? normalizedLineId,
        }
        return previous.map((favorite) => (favorite.id === id ? updated : favorite))
      })

      return id
    },
    [filters, sections, normalizedLineId]
  )

  const applyFavorite = React.useCallback(
    (id) => {
      const target = favoritesByLine.find((favorite) => favorite.id === id)
      if (!target) return
      const sanitizedFilters = sanitizeFilters(target.filters, sections)
      replaceFilters(sanitizedFilters)
    },
    [favoritesByLine, sections, replaceFilters]
  )

  const deleteFavorite = React.useCallback((id) => {
    setFavorites((previous) => previous.filter((favorite) => favorite.id !== id))
  }, [])

  return {
    favorites: favoritesByLine,
    saveFavorite,
    updateFavorite,
    applyFavorite,
    deleteFavorite,
  }
}
