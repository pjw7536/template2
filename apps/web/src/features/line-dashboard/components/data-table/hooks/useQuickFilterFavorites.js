// src/features/line-dashboard/components/data-table/hooks/useQuickFilterFavorites.js
import * as React from "react"

import {
  createInitialQuickFilters,
  syncQuickFiltersToSections,
} from "../filters/quickFilters"

const STORAGE_KEY_PREFIX = "line-dashboard:quick-filter-favorites"
const DEFAULT_OWNER = "anonymous"

const hasWindow = typeof window !== "undefined"

function makeStorageKey(ownerId) {
  const safeOwner = ownerId ? String(ownerId).trim().toLowerCase() : DEFAULT_OWNER
  return `${STORAGE_KEY_PREFIX}:${safeOwner}`
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

function loadFavorites(storageKey, sections) {
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
        return { id, name, filters: sanitizeFilters(entry.filters, sections) }
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

export function useQuickFilterFavorites({ filters, sections, replaceFilters, ownerId }) {
  const storageKey = React.useMemo(() => makeStorageKey(ownerId), [ownerId])

  const [favorites, setFavorites] = React.useState(() =>
    loadFavorites(storageKey, sections)
  )

  React.useEffect(() => {
    setFavorites(loadFavorites(storageKey, sections))
  }, [storageKey, sections])

  React.useEffect(() => {
    setFavorites((previous) => {
      const shouldSanitize = Array.isArray(sections) && sections.length > 0
      if (!shouldSanitize) return previous
      return previous.map((favorite) => ({
        ...favorite,
        filters: sanitizeFilters(favorite.filters, sections),
      }))
    })
  }, [sections])

  React.useEffect(() => {
    persistFavorites(storageKey, favorites)
  }, [favorites, storageKey])

  const saveFavorite = React.useCallback(
    (name) => {
      const trimmed = typeof name === "string" ? name.trim() : ""
      if (!trimmed) return
      const sanitizedFilters = sanitizeFilters(filters, sections)

      let createdId = null

      setFavorites((previous) => {
        const existingIndex = previous.findIndex(
          (favorite) => favorite.name.toLowerCase() === trimmed.toLowerCase()
        )

        if (existingIndex >= 0) {
          return previous
        }

        const nextFavorite = {
          id: createId(),
          name: trimmed,
          filters: sanitizedFilters,
        }

        createdId = nextFavorite.id

        return [...previous, nextFavorite]
      })

      return createdId
    },
    [filters, sections]
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
        const updated = { ...target, name: trimmed, filters: sanitizedFilters }
        return previous.map((favorite) => (favorite.id === id ? updated : favorite))
      })

      return id
    },
    [filters, sections]
  )

  const applyFavorite = React.useCallback(
    (id) => {
      const target = favorites.find((favorite) => favorite.id === id)
      if (!target) return
      const sanitizedFilters = sanitizeFilters(target.filters, sections)
      replaceFilters(sanitizedFilters)
    },
    [favorites, sections, replaceFilters]
  )

  const deleteFavorite = React.useCallback((id) => {
    setFavorites((previous) => previous.filter((favorite) => favorite.id !== id))
  }, [])

  return {
    favorites,
    saveFavorite,
    updateFavorite,
    applyFavorite,
    deleteFavorite,
  }
}
