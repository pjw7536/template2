// src/features/line-dashboard/components/data-table/hooks/useQuickFilters.js
import * as React from "react"

import {
  applyQuickFilters,
  countActiveQuickFilters,
  createInitialQuickFilters,
  createQuickFilterSections,
  isMultiSelectFilter,
  syncQuickFiltersToSections,
} from "../filters/quickFilters"

/**
 * 퀵 필터 섹션 상태를 생성·유지하고, 적용된 필터에 맞는 행 목록을 돌려주는 훅입니다.
 */
export function useQuickFilters(columns, rows, options = {}) {
  // 컬럼/행 데이터를 기반으로 어떤 퀵 필터 섹션이 필요한지 계산합니다.
  const sections = React.useMemo(
    () => createQuickFilterSections(columns, rows, options),
    [columns, rows, options]
  )

  // 필터 상태는 섹션 구조에 맞춰 기본값을 생성해 둡니다.
  const [filters, setFilters] = React.useState(() => createInitialQuickFilters())

  // 컬럼이 바뀌면 섹션도 바뀌므로, 기존 상태를 새 구조에 맞춰 정리합니다.
  React.useEffect(() => {
    setFilters((previous) =>
      syncQuickFiltersToSections(previous, sections, { preserveMissing: true })
    )
  }, [sections])

  // 실제로 퀵 필터를 적용한 행 목록입니다.
  const filteredRows = React.useMemo(
    () => applyQuickFilters(rows, sections, filters),
    [rows, sections, filters]
  )

  // 현재 몇 개의 필터가 활성화되어 있는지 카운트합니다.
  const activeCount = React.useMemo(
    () => countActiveQuickFilters(filters, sections),
    [filters, sections]
  )

  // 단일 선택/다중 선택 필터를 구분하여 토글 동작을 정의합니다.
  const toggleFilter = React.useCallback((key, value, options = {}) => {
    setFilters((previous) => {
      const isMulti = isMultiSelectFilter(key)
      const forceValue = Boolean(options.forceValue)
      if (value === null) {
        return { ...previous, [key]: isMulti ? [] : null }
      }

      if (!isMulti) {
        if (forceValue) {
          return { ...previous, [key]: value }
        }
        return { ...previous, [key]: previous[key] === value ? null : value }
      }

      if (forceValue) {
        const nextValues = Array.isArray(value) ? value : []
        return { ...previous, [key]: nextValues }
      }

      const currentValues = Array.isArray(previous[key]) ? previous[key] : []
      const exists = currentValues.includes(value)
      const nextValues = exists
        ? currentValues.filter((item) => item !== value)
        : [...currentValues, value]

      return { ...previous, [key]: nextValues }
    })
  }, [])

  const resetFilters = React.useCallback(
    () => setFilters(createInitialQuickFilters()),
    []
  )

  const replaceFilters = React.useCallback(
    (nextFilters, options = { preserveMissing: true }) => {
      setFilters(() => {
        const base = createInitialQuickFilters()
        const merged = { ...base, ...(nextFilters ?? {}) }
        const hasSections = Array.isArray(sections) && sections.length > 0
        return hasSections
          ? syncQuickFiltersToSections(merged, sections, options)
          : merged
      })
    },
    [sections]
  )

  return {
    sections,
    filters,
    filteredRows,
    activeCount,
    toggleFilter,
    resetFilters,
    replaceFilters,
  }
}
