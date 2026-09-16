// src/features/line-dashboard/utils/recentHoursSlider.js
// 퀵 필터의 "최근시간" 슬라이더 포지션을 시간 범위와 변환하는 유틸입니다.
import {
  RECENT_HOURS_DAY_MODE_MAX_DAYS,
  RECENT_HOURS_DAY_MODE_MIN_DAYS,
  RECENT_HOURS_DAY_MODE_THRESHOLD,
  RECENT_HOURS_DAY_STEP,
  clampRecentHours,
  createRecentHoursRange,
  normalizeRecentHoursRange,
  snapRecentHours,
} from "./dataTableQuickFilters"

export const RECENT_SLIDER_MIN = 0
export const RECENT_SLIDER_MAX = 100
export const RECENT_SLIDER_STEP = 1
export const RECENT_SLIDER_SPLIT = RECENT_SLIDER_MAX / 2

const DAY_SEGMENT_MAX_POSITION = RECENT_SLIDER_SPLIT - RECENT_SLIDER_STEP

const MIN_DAY_HOURS = RECENT_HOURS_DAY_MODE_MIN_DAYS * RECENT_HOURS_DAY_STEP
const MAX_DAY_HOURS = RECENT_HOURS_DAY_MODE_MAX_DAYS * RECENT_HOURS_DAY_STEP

export function rangeToSliderPositions(range) {
  const normalized = normalizeRecentHoursRange(range)
  return [
    hoursToSliderPosition(normalized.start),
    hoursToSliderPosition(normalized.end),
  ]
}

export function sliderPositionsToRange(positions) {
  if (!Array.isArray(positions) || positions.length === 0) {
    return createRecentHoursRange()
  }
  const sorted = [...positions].slice(0, 2).sort((a, b) => a - b)
  const [left = RECENT_SLIDER_MIN, right = left] = sorted
  const startHours = sliderPositionToHours(left)
  const endHours = sliderPositionToHours(right)
  return createRecentHoursRange(startHours, endHours)
}

export function formatRecentHoursRange(range) {
  const normalized = normalizeRecentHoursRange(range)
  return `${formatHoursAgo(normalized.start)} ~ ${formatHoursAgo(normalized.end)}`
}

export function formatHoursAgo(hours) {
  const snapped = snapRecentHours(hours)
  if (snapped <= 0) return "현재"
  if (snapped > RECENT_HOURS_DAY_MODE_THRESHOLD) {
    const days = Math.round(snapped / RECENT_HOURS_DAY_STEP)
    return `-${days}d`
  }
  return `-${snapped}h`
}

function hoursToSliderPosition(hours) {
  const snapped = snapSliderHours(hours)
  if (snapped <= RECENT_HOURS_DAY_MODE_THRESHOLD) {
    const fraction =
      (RECENT_HOURS_DAY_MODE_THRESHOLD - snapped) / RECENT_HOURS_DAY_MODE_THRESHOLD
    const position =
      RECENT_SLIDER_SPLIT +
      fraction * (RECENT_SLIDER_MAX - RECENT_SLIDER_SPLIT)
    return clampSliderPosition(position)
  }

  const days = snapped / RECENT_HOURS_DAY_STEP
  const daySpan = RECENT_HOURS_DAY_MODE_MAX_DAYS - RECENT_HOURS_DAY_MODE_MIN_DAYS
  if (daySpan <= 0) return clampSliderPosition(RECENT_SLIDER_MIN)

  const fraction = (RECENT_HOURS_DAY_MODE_MAX_DAYS - days) / daySpan
  const position = fraction * DAY_SEGMENT_MAX_POSITION
  return clampSliderPosition(position)
}

function sliderPositionToHours(position) {
  const clamped = clampSliderPosition(position)
  if (clamped >= RECENT_SLIDER_SPLIT) {
    const fraction =
      (clamped - RECENT_SLIDER_SPLIT) / (RECENT_SLIDER_MAX - RECENT_SLIDER_SPLIT)
    const hours =
      RECENT_HOURS_DAY_MODE_THRESHOLD -
      fraction * RECENT_HOURS_DAY_MODE_THRESHOLD
    return snapSliderHours(hours)
  }

  const daySpan = RECENT_HOURS_DAY_MODE_MAX_DAYS - RECENT_HOURS_DAY_MODE_MIN_DAYS
  if (daySpan <= 0) {
    return snapSliderHours(MAX_DAY_HOURS)
  }

  const fraction = clamped / DAY_SEGMENT_MAX_POSITION
  const days =
    RECENT_HOURS_DAY_MODE_MAX_DAYS - fraction * daySpan
  const roundedDays = Math.round(days)
  const boundedDays = Math.min(
    Math.max(roundedDays, RECENT_HOURS_DAY_MODE_MIN_DAYS),
    RECENT_HOURS_DAY_MODE_MAX_DAYS
  )
  return snapSliderHours(boundedDays * RECENT_HOURS_DAY_STEP)
}

function clampSliderPosition(value) {
  if (!Number.isFinite(value)) return RECENT_SLIDER_MIN
  const rounded = Math.round(value / RECENT_SLIDER_STEP) * RECENT_SLIDER_STEP
  return Math.min(Math.max(rounded, RECENT_SLIDER_MIN), RECENT_SLIDER_MAX)
}

function snapSliderHours(value) {
  const clamped = clampRecentHours(value)
  if (clamped <= RECENT_HOURS_DAY_MODE_THRESHOLD) {
    return Math.round(clamped)
  }

  const rawDays = Math.round(clamped / RECENT_HOURS_DAY_STEP)
  const boundedDays = Math.min(
    Math.max(rawDays, RECENT_HOURS_DAY_MODE_MIN_DAYS),
    RECENT_HOURS_DAY_MODE_MAX_DAYS
  )
  const snappedHours = boundedDays * RECENT_HOURS_DAY_STEP
  return Math.min(Math.max(snappedHours, MIN_DAY_HOURS), MAX_DAY_HOURS)
}
