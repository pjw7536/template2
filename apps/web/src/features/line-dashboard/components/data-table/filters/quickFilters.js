// src/features/line-dashboard/components/data-table/filters/quickFilters.js
// 퀵 필터 섹션을 생성하고 적용하는 로직입니다.
import { STATUS_LABELS } from "../../../constants/status-labels"

const STATUS_ORDER = Object.keys(STATUS_LABELS)
const STATUS_ORDER_INDEX = new Map(STATUS_ORDER.map((status, index) => [status, index]))

const MULTI_SELECT_KEYS = new Set(["status"])

const HOUR_IN_MS = 60 * 60 * 1000
const FUTURE_TOLERANCE_MS = 5 * 60 * 1000

const RECENT_HOUR_OPTIONS = [
  { value: "12", label: "~12시간" },
  { value: "24", label: "~24시간" },
  { value: "36", label: "~36시간" },
]

function findMatchingColumn(columns, target) {
  if (!Array.isArray(columns)) return null
  const targetLower = target.toLowerCase()
  return (
    columns.find((column) => typeof column === "string" && column.toLowerCase() === targetLower) ??
    null
  )
}

function normalizeBooleanValue(value) {
  if (typeof value === "boolean") return value
  if (value === null || value === undefined) return null
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value === 1) return true
    if (value === 0) return false
    return null
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (!normalized) return null
    if (["1", "true", "t", "y", "yes"].includes(normalized)) return true
    if (["0", "false", "f", "n", "no"].includes(normalized)) return false
    return null
  }
  if (typeof value === "bigint") {
    if (value === 1n) return true
    if (value === 0n) return false
  }
  return null
}

function toTimestamp(value) {
  if (value == null) return null

  if (value instanceof Date) {
    const time = value.getTime()
    return Number.isNaN(time) ? null : time
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.length === 0) return null

    const numeric = Number(trimmed)
    if (Number.isFinite(numeric)) {
      return numeric
    }

    const parsed = new Date(trimmed)
    const time = parsed.getTime()
    return Number.isNaN(time) ? null : time
  }

  const parsed = new Date(value)
  const time = parsed.getTime()
  return Number.isNaN(time) ? null : time
}

const QUICK_FILTER_DEFINITIONS = [
  {
    key: "recent_hours",
    label: "최근시간",
    resolveColumn: (columns) =>
      findMatchingColumn(columns, "created_at") ?? findMatchingColumn(columns, "updated_at"),
    buildSection: ({ columns }) => {
      const columnKey =
        findMatchingColumn(columns, "created_at") ?? findMatchingColumn(columns, "updated_at")
      if (!columnKey) return null

      const getValue = (row) => row?.[columnKey] ?? null

      return {
        options: RECENT_HOUR_OPTIONS.map((option) => ({ ...option })),
        getValue,
        matchRow: (row, current) => {
          if (current === null) return true

          const hours = Number(current)
          if (!Number.isFinite(hours) || hours <= 0) return true

          const timestamp = toTimestamp(getValue(row))
          if (timestamp === null) return false

          const now = Date.now()
          const minTimestamp = now - hours * HOUR_IN_MS
          const maxTimestamp = now + FUTURE_TOLERANCE_MS

          return timestamp >= minTimestamp && timestamp <= maxTimestamp
        },
      }
    },
  },
  {
    key: "status",
    label: "Status",
    resolveColumn: (columns) => findMatchingColumn(columns, "status"),
    normalizeValue: (value) => {
      if (value == null) return null
      const normalized = String(value).trim()
      return normalized.length > 0 ? normalized.toUpperCase() : null
    },
    formatValue: (value) => STATUS_LABELS[value] ?? value,
    compareOptions: (a, b) => {
      const indexA = STATUS_ORDER_INDEX.has(a.value)
        ? STATUS_ORDER_INDEX.get(a.value)
        : Number.POSITIVE_INFINITY
      const indexB = STATUS_ORDER_INDEX.has(b.value)
        ? STATUS_ORDER_INDEX.get(b.value)
        : Number.POSITIVE_INFINITY
      if (indexA !== indexB) return indexA - indexB
      return a.label.localeCompare(b.label, undefined, { sensitivity: "base" })
    },
  },
  {
    key: "needtosend",
    label: "예약",
    resolveColumn: (columns) => findMatchingColumn(columns, "needtosend"),
    normalizeValue: normalizeBooleanValue,
    formatValue: (value) => (value ? "Yes" : "No"),
    compareOptions: (a, b) => {
      if (a.value === b.value) return 0
      if (a.value === true) return -1
      if (b.value === true) return 1
      return 0
    },
  },
  {
    key: "send_jira",
    label: "Jira전송완료",
    resolveColumn: (columns) => findMatchingColumn(columns, "send_jira"),
    normalizeValue: normalizeBooleanValue,
    formatValue: (value) => (value ? "Yes" : "No"),
    compareOptions: (a, b) => {
      if (a.value === b.value) return 0
      if (a.value === true) return -1
      if (b.value === true) return 1
      return 0
    },
  },
  {
    key: "sdwt_prod",
    label: "설비분임조",
    resolveColumn: (columns) => findMatchingColumn(columns, "sdwt_prod"),
    normalizeValue: (value) => {
      if (value == null) return null
      const trimmed = String(value).trim()
      return trimmed.length > 0 ? trimmed : null
    },
    formatValue: (value) => value,
    compareOptions: (a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
  },
  {
    key: "user_sdwt_prod",
    label: "Engr분임조",
    resolveColumn: (columns) => findMatchingColumn(columns, "user_sdwt_prod"),
    normalizeValue: (value) => {
      if (value == null) return null
      const trimmed = String(value).trim()
      return trimmed.length > 0 ? trimmed : null
    },
    formatValue: (value) => value,
    compareOptions: (a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
  },

  // 🔹 sample_type 퀵필터 (멀티 선택)
  {
    key: "sample_type",
    label: "Sample Type",
    resolveColumn: (columns) => findMatchingColumn(columns, "sample_type"),
    normalizeValue: (value) => {
      if (value == null) return null
      const trimmed = String(value).trim()
      return trimmed.length > 0 ? trimmed : null
    },
    formatValue: (value) => value,
    compareOptions: (a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
  },


]

// 섹션 정의에 맞춰 초기 필터 상태(단일 null, 다중 [])를 만듭니다.
export function createInitialQuickFilters() {
  return QUICK_FILTER_DEFINITIONS.reduce((acc, definition) => {
    acc[definition.key] = MULTI_SELECT_KEYS.has(definition.key) ? [] : null
    return acc
  }, {})
}

// 컬럼/행 데이터를 기반으로 퀵 필터 섹션 목록을 생성합니다.
export function createQuickFilterSections(columns, rows) {
  return QUICK_FILTER_DEFINITIONS.map((definition) => {
    if (typeof definition.buildSection === "function") {
      const section = definition.buildSection({ columns, rows })
      if (!section) return null
      return {
        key: definition.key,
        label: definition.label,
        isMulti: MULTI_SELECT_KEYS.has(definition.key),
        ...section,
      }
    }

    const columnKey = definition.resolveColumn(columns)
    if (!columnKey) return null

    const valueMap = new Map()
    rows.forEach((row) => {
      const rawValue = row?.[columnKey]
      const normalized = definition.normalizeValue(rawValue)
      if (normalized === null) return
      if (!valueMap.has(normalized)) {
        valueMap.set(normalized, definition.formatValue(normalized, rawValue))
      }
    })

    if (valueMap.size === 0) return null

    const options = Array.from(valueMap.entries()).map(([value, label]) => ({ value, label }))
    if (typeof definition.compareOptions === "function") {
      options.sort((a, b) => definition.compareOptions(a, b))
    }

    const isMulti = MULTI_SELECT_KEYS.has(definition.key)
    const getValue = (row) => definition.normalizeValue(row?.[columnKey])

    return {
      key: definition.key,
      label: definition.label,
      options,
      getValue,
      isMulti,
      matchRow: (row, current) => {
        const rowValue = getValue(row)
        if (isMulti) {
          return Array.isArray(current) && current.length > 0 ? current.includes(rowValue) : true
        }
        return current !== null ? rowValue === current : true
      },
    }
  }).filter(Boolean)
}

// 섹션 구성 변경 시 기존 상태를 정리해 일관성을 유지합니다.
export function syncQuickFiltersToSections(previousFilters, sections) {
  const sectionMap = new Map(sections.map((section) => [section.key, section]))
  let nextFilters = previousFilters

  QUICK_FILTER_DEFINITIONS.forEach((definition) => {
    const section = sectionMap.get(definition.key)
    const current = previousFilters[definition.key]
    const shouldBeMulti = MULTI_SELECT_KEYS.has(definition.key)

    if (!section) {
      const resetValue = shouldBeMulti ? [] : null
      if (JSON.stringify(current) !== JSON.stringify(resetValue)) {
        if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
        nextFilters[definition.key] = resetValue
      }
      return
    }

    const validValues = new Set(section.options.map((option) => option.value))
    if (section.isMulti) {
      const currentArray = Array.isArray(current) ? current : []
      const filtered = currentArray.filter((value) => validValues.has(value))
      if (filtered.length !== currentArray.length) {
        if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
        nextFilters[definition.key] = filtered
      }
    } else if (current !== null && !validValues.has(current)) {
      if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
      nextFilters[definition.key] = null
    }
  })

  return nextFilters
}

// 생성된 섹션/필터를 rows 배열에 실제로 적용합니다.
export function applyQuickFilters(rows, sections, filters) {
  if (sections.length === 0) return rows
  return rows.filter((row) =>
    sections.every((section) => {
      const current = filters[section.key]
      if (typeof section.matchRow === "function") {
        return section.matchRow(row, current)
      }
      const rowValue = typeof section.getValue === "function" ? section.getValue(row) : null
      if (section.isMulti) {
        return Array.isArray(current) && current.length > 0 ? current.includes(rowValue) : true
      }
      return current !== null ? rowValue === current : true
    })
  )
}

// 현재 활성화되어 있는 필터 개수를 센 뒤 배지에 표시합니다.
export function countActiveQuickFilters(filters) {
  return Object.entries(filters).reduce((sum, [key, value]) => {
    if (MULTI_SELECT_KEYS.has(key)) {
      return sum + (Array.isArray(value) ? value.length : 0)
    }
    return sum + (value !== null ? 1 : 0)
  }, 0)
}

// 해당 키가 다중 선택 옵션인지 여부를 확인합니다.
export function isMultiSelectFilter(key) {
  return MULTI_SELECT_KEYS.has(key)
}

export { QUICK_FILTER_DEFINITIONS }
