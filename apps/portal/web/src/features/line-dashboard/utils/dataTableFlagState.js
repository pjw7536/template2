const TINY_INT_MIN = -128
const TINY_INT_MAX = 127

function clampTinyInt(value) {
  return Math.max(TINY_INT_MIN, Math.min(TINY_INT_MAX, Math.trunc(value)))
}

export function toTinyIntFlag(rawValue, defaultValue = 0) {
  if (rawValue === null || rawValue === undefined) return defaultValue

  if (typeof rawValue === "boolean") return rawValue ? 1 : 0

  if (typeof rawValue === "number" && Number.isFinite(rawValue)) {
    return clampTinyInt(rawValue)
  }

  if (typeof rawValue === "bigint") {
    return clampTinyInt(Number(rawValue))
  }

  const normalized = String(rawValue).trim().toLowerCase()
  if (!normalized) return defaultValue

  if (["1", "true", "t", "y", "yes", "on"].includes(normalized)) return 1
  if (["0", "false", "f", "n", "no", "off"].includes(normalized)) return 0

  const parsed = Number.parseInt(normalized, 10)
  if (Number.isFinite(parsed)) return clampTinyInt(parsed)

  return defaultValue
}

export function deriveFlagState(rawValue, defaultValue = 0) {
  const numericValue = toTinyIntFlag(rawValue, defaultValue)
  const isOn = numericValue > 0
  const isError = numericValue < 0
  const state = isError ? "error" : isOn ? "on" : "off"

  return { numericValue, isOn, isError, state }
}

export function describeFlagState(rawValue, defaultValue = 0) {
  const { state } = deriveFlagState(rawValue, defaultValue)
  if (state === "error") return "예약오류"
  if (state === "on") return "예약완료"
  return "예약안됨"
}
