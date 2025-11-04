// Shared constants used across the line dashboard API helpers.
// Splitting these values out keeps the logic-focused modules easier to scan.
export const SAFE_IDENTIFIER = /^[A-Za-z0-9_]+$/

export const DATE_ONLY_REGEX = /^\d{4}-\d{2}-\d{2}$/

export const DATE_COLUMN_CANDIDATES = [
  "created_at",
  "updated_at",
  "timestamp",
  "ts",
  "date",
]

export const LINE_SDWT_TABLE_NAME = "line_sdwt"
