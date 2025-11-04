import { DATE_ONLY_REGEX, SAFE_IDENTIFIER } from "./constants"

/**
 * Sanitises table or column identifiers by ensuring they only contain
 * alphanumeric characters or underscores. When invalid input is provided a
 * configurable fallback value is returned instead of throwing.
 */
export function sanitizeIdentifier(value, fallback = null) {
  if (typeof value !== "string") return fallback
  const trimmed = value.trim()
  return SAFE_IDENTIFIER.test(trimmed) ? trimmed : fallback
}

/**
 * Normalises YYYY-MM-DD query parameters by trimming whitespace and verifying
 * the expected format. Invalid values are ignored by returning null.
 */
export function normalizeDateOnly(value) {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return DATE_ONLY_REGEX.test(trimmed) ? trimmed : null
}
