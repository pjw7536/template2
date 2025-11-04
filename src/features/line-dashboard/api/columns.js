import { DATE_COLUMN_CANDIDATES } from "./constants"

/**
 * Finds a column in a case-insensitive manner while preserving the original
 * casing from the database result set.
 */
export function findColumn(columnNames, target) {
  const targetLower = String(target || "").toLowerCase()
  for (const name of columnNames) {
    if (typeof name !== "string") continue
    if (name.toLowerCase() === targetLower) return name
  }
  return null
}

/**
 * Picks the best timestamp column by walking a list of candidate names in
 * priority order. Returns null when no candidate exists.
 */
export function pickBaseTimestampColumn(columnNames) {
  for (const candidate of DATE_COLUMN_CANDIDATES) {
    const found = findColumn(columnNames, candidate)
    if (found) return found
  }
  return null
}
