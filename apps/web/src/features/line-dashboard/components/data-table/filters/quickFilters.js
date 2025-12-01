// src/features/line-dashboard/components/data-table/filters/quickFilters.js
// 퀵 필터 섹션을 생성하고 적용하는 로직입니다.
import { STATUS_LABELS, STATUS_SEQUENCE } from "../../../constants/status-labels"
import { deriveFlagState } from "../utils/flagState"

const STATUS_ORDER = STATUS_SEQUENCE
const STATUS_ORDER_INDEX = new Map(STATUS_ORDER.map((status, index) => [status, index]))

const MULTI_SELECT_KEYS = new Set(["status", "sample_type", "sample_group", "main_step"])

const HOUR_IN_MS = 60 * 60 * 1000
const FUTURE_TOLERANCE_MS = 5 * 60 * 1000

export const RECENT_HOURS_MIN = 0
export const RECENT_HOURS_MAX = 36
export const RECENT_HOURS_DEFAULT_START = 8
export const RECENT_HOURS_DEFAULT_END = 0

const DEFAULT_FILTER_VALUES = {
  recent_hours: () => createRecentHoursRange(),
}

function isDefaultRecentHours(value) {
  const normalized = normalizeRecentHoursRange(value)
  const defaults = createRecentHoursRange()
  return normalized.start === defaults.start && normalized.end === defaults.end
}

function findMatchingColumn(columns, target) {
  if (!Array.isArray(columns)) return null
  const targetLower = target.toLowerCase()
  return (
    columns.find((column) => typeof column === "string" && column.toLowerCase() === targetLower) ??
    null
  )
}

function normalizeFlagState(value) {
  if (value === null || value === undefined) return null
  const { state } = deriveFlagState(value, 0)
  return state
}

function normalizeEmailId(value) {
  if (value == null) return ""
  const trimmed = String(value).trim()
  if (!trimmed) return ""
  const lowered = trimmed.toLowerCase()
  const atIndex = lowered.indexOf("@")
  if (atIndex === -1) return lowered
  return lowered.slice(0, atIndex)
}

function deriveUserIdFromEmail(email) {
  const normalized = normalizeEmailId(email)
  return normalized || null
}

function normalizeMainStep(value) {
  if (value == null) return null
  const trimmed = String(value).trim()
  return trimmed.length > 0 ? trimmed : null
}

function parseMainStepParts(value) {
  const normalized = normalizeMainStep(value) ?? ""
  const prefix = normalized.slice(0, 2)
  const numericPart = normalized.slice(2)
  const number = Number.parseInt(numericPart, 10)
  return {
    prefix,
    number: Number.isFinite(number) ? number : Number.POSITIVE_INFINITY,
    raw: normalized,
  }
}

function compareMainStepOptions(a, b) {
  const left = parseMainStepParts(a.value)
  const right = parseMainStepParts(b.value)

  if (left.number !== right.number) {
    return left.number - right.number
  }

  const prefixCompare = left.prefix.localeCompare(right.prefix, undefined, { sensitivity: "base" })
  if (prefixCompare !== 0) return prefixCompare

  return a.label.localeCompare(b.label, undefined, { sensitivity: "base" })
}

function sanitizeMainStepFilters(values, section) {
  const normalizedArray = Array.isArray(values)
    ? values
    : values === null || values === undefined
      ? []
      : [values]

  const options = Array.isArray(section?.options) ? section.options : []
  const optionValues = options.map((option) => option.value)
  const optionSet = new Set(optionValues)
  const resolved = []

  normalizedArray.forEach((value) => {
    const normalized = normalizeMainStep(value)
    if (!normalized) return

    if (optionSet.size === 0 || optionSet.has(normalized)) {
      resolved.push(normalized)
    }
  })

  return Array.from(new Set(resolved))
}

function arraysShallowEqual(a, b) {
  if (a === b) return true
  if (!Array.isArray(a) || !Array.isArray(b)) return false
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false
  }
  return true
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

export function clampRecentHours(value) {
  if (!Number.isFinite(value)) return RECENT_HOURS_MIN
  return Math.min(Math.max(value, RECENT_HOURS_MIN), RECENT_HOURS_MAX)
}

export function createRecentHoursRange(
  start = RECENT_HOURS_DEFAULT_START,
  end = RECENT_HOURS_DEFAULT_END
) {
  const numericStart = Number(start)
  const numericEnd = Number(end)
  const safeStart = clampRecentHours(
    Number.isFinite(numericStart) ? numericStart : RECENT_HOURS_DEFAULT_START
  )
  const safeEnd = clampRecentHours(
    Number.isFinite(numericEnd) ? numericEnd : RECENT_HOURS_DEFAULT_END
  )
  if (safeStart < safeEnd) {
    return { start: safeEnd, end: safeEnd }
  }
  return { start: safeStart, end: safeEnd }
}

export function normalizeRecentHoursRange(value) {
  if (value === null || value === undefined) {
    return createRecentHoursRange()
  }

  if (Array.isArray(value)) {
    const [rawStart, rawEnd] = value
    return createRecentHoursRange(rawStart, rawEnd === undefined ? rawStart : rawEnd)
  }

  if (typeof value === "object") {
    const rawStart =
      value.start ?? value.from ?? value.max ?? value.begin ?? value[0]
    const rawEnd = value.end ?? value.to ?? value.min ?? value.finish ?? value[1]
    return createRecentHoursRange(rawStart, rawEnd)
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return createRecentHoursRange()
    const parts = trimmed.split(/[:,]/).map((part) => part.trim())
    if (parts.length >= 2) {
      return createRecentHoursRange(parts[0], parts[1])
    }
    const numeric = Number(trimmed)
    if (Number.isFinite(numeric)) {
      return createRecentHoursRange(numeric, RECENT_HOURS_DEFAULT_END)
    }
    return createRecentHoursRange()
  }

  const numeric = Number(value)
  return Number.isFinite(numeric)
    ? createRecentHoursRange(numeric, RECENT_HOURS_DEFAULT_END)
    : createRecentHoursRange()
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
        options: [],
        getValue,
        allowCustomValue: true,
        matchRow: (row, current) => {
          if (current === null) return true

          const range = normalizeRecentHoursRange(current)
          const timestamp = toTimestamp(getValue(row))
          if (timestamp === null) return false

          const now = Date.now()
          const minTimestamp = now - range.start * HOUR_IN_MS
          const maxTimestamp = now - range.end * HOUR_IN_MS + FUTURE_TOLERANCE_MS

          return timestamp >= minTimestamp && timestamp <= maxTimestamp
        },
      }
    },
  },

  {
    key: "my_sop",
    label: "MySop",
    buildSection: ({ columns, options }) => {
      const columnKey = findMatchingColumn(columns, "knoxid")
      const userId = deriveUserIdFromEmail(options?.currentUserEmail)
      if (!columnKey || !userId) return null

      const normalizedUserId = userId.toLowerCase()
      const getValue = (row) => row?.[columnKey] ?? null

      return {
        options: [],
        getValue,
        allowCustomValue: true,
        userId: normalizedUserId,
        matchRow: (row, current) => {
          if (!current) return true
          const normalizedKnoxid = normalizeEmailId(getValue(row))
          if (!normalizedKnoxid) return false
          return normalizedKnoxid.toLowerCase() === normalizedUserId
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
    normalizeValue: normalizeFlagState,
    formatValue: (value) => {
      return value === "on" ? "Y" : "N"
    },
    compareOptions: (a, b) => {
      const order = { on: 0, off: 1 }
      const orderA = order[a.value] ?? 99
      const orderB = order[b.value] ?? 99
      if (orderA !== orderB) return orderA - orderB
      return String(a.value).localeCompare(String(b.value))
    },
  },
  {
    key: "send_jira",
    label: "Jira전송완료",
    resolveColumn: (columns) => findMatchingColumn(columns, "send_jira"),
    normalizeValue: normalizeFlagState,
    formatValue: (value) => {
      if (value === "on") return "Y"
      if (value === "off") return "N"
      if (value === "error") return "Error"
      return String(value)
    },
    compareOptions: (a, b) => {
      const order = { on: 0, off: 1, error: 2 }
      const orderA = order[a.value] ?? 99
      const orderB = order[b.value] ?? 99
      if (orderA !== orderB) return orderA - orderB
      return String(a.value).localeCompare(String(b.value))
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
    key: "main_step",
    label: "Main Step",
    buildSection: ({ columns, rows }) => {
      const columnKey = findMatchingColumn(columns, "main_step")
      if (!columnKey) return null

      const valueSet = new Set()
      rows.forEach((row) => {
        const normalized = normalizeMainStep(row?.[columnKey])
        if (normalized) {
          valueSet.add(normalized)
        }
      })

      const options = Array.from(valueSet).map((value) => ({
        value,
        label: value,
      }))

      options.sort(compareMainStepOptions)

      const getValue = (row) => normalizeMainStep(row?.[columnKey])

      return {
        options,
        getValue,
        allowCustomValue: false,
      }
    },
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
  {
    key: "sample_group",
    label: "Sample Group",
    resolveColumn: (columns) => findMatchingColumn(columns, "sample_group"),
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
    if (MULTI_SELECT_KEYS.has(definition.key)) {
      acc[definition.key] = []
    } else {
      const defaultValue = DEFAULT_FILTER_VALUES[definition.key]
      if (typeof defaultValue === "function") {
        acc[definition.key] = defaultValue()
      } else {
        acc[definition.key] = defaultValue ?? null
      }
    }
    return acc
  }, {})
}

// 컬럼/행 데이터를 기반으로 퀵 필터 섹션 목록을 생성합니다.
export function createQuickFilterSections(columns, rows, options = {}) {
  return QUICK_FILTER_DEFINITIONS.map((definition) => {
    if (typeof definition.buildSection === "function") {
      const section = definition.buildSection({ columns, rows, options })
      if (!section) return null
      const { allowCustomValue = false, ...restSection } = section
      return {
        key: definition.key,
        label: definition.label,
        isMulti: MULTI_SELECT_KEYS.has(definition.key),
        allowCustomValue,
        ...restSection,
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

    let sectionOptions = []

    if (valueMap.size > 0) {
      sectionOptions = Array.from(valueMap.entries()).map(([value, label]) => ({
        value,
        label,
      }))

      if (typeof definition.compareOptions === "function") {
        sectionOptions.sort((a, b) => definition.compareOptions(a, b))
      }
    }

    const isMulti = MULTI_SELECT_KEYS.has(definition.key)
    const getValue = (row) => definition.normalizeValue(row?.[columnKey])

    return {
      key: definition.key,
      label: definition.label,
      options: sectionOptions,
      getValue,
      isMulti,
      allowCustomValue: false,
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
export function syncQuickFiltersToSections(previousFilters, sections, options = {}) {
  const preserveMissing = Boolean(options?.preserveMissing)
  const sectionMap = new Map(sections.map((section) => [section.key, section]))
  let nextFilters = previousFilters

  QUICK_FILTER_DEFINITIONS.forEach((definition) => {
    const section = sectionMap.get(definition.key)
    const current = previousFilters[definition.key]
    const shouldBeMulti = MULTI_SELECT_KEYS.has(definition.key)

    if (!section) {
      if (preserveMissing) return
      const resetValue = shouldBeMulti ? [] : null
      if (JSON.stringify(current) !== JSON.stringify(resetValue)) {
        if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
        nextFilters[definition.key] = resetValue
      }
      return
    }

    if (section.isMulti) {
      const normalizedArray = Array.isArray(current)
        ? current
        : current === null || current === undefined
          ? []
          : [current]

      const finalValues =
        definition.key === "main_step"
          ? sanitizeMainStepFilters(normalizedArray, section)
          : normalizedArray

      if (!arraysShallowEqual(finalValues, current)) {
        if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
        nextFilters[definition.key] = finalValues
      }
      return
    }

    if (definition.key === "recent_hours") {
      if (current === null) return
      const normalized = normalizeRecentHoursRange(current)
      const isShallowEqual =
        typeof current === "object" &&
        current !== null &&
        current.start === normalized.start &&
        current.end === normalized.end
      if (!isShallowEqual) {
        if (nextFilters === previousFilters) nextFilters = { ...previousFilters }
        nextFilters[definition.key] = normalized
      }
      return
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
export function countActiveQuickFilters(filters, sections = null) {
  const allowedKeys =
    Array.isArray(sections) && sections.length > 0 ? new Set(sections.map((section) => section.key)) : null

  return Object.entries(filters).reduce((sum, [key, value]) => {
    if (allowedKeys && !allowedKeys.has(key)) return sum

    if (key === "recent_hours") {
      return sum + (value !== null && !isDefaultRecentHours(value) ? 1 : 0)
    }
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
