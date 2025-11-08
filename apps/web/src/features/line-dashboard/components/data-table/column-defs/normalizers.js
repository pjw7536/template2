// src/features/line-dashboard/components/data-table/column-defs/normalizers.js
// 셀 렌더러에서 공통으로 쓰는 값 정규화 유틸입니다.

export function toHttpUrl(raw) {
  if (raw == null) return null
  const value = String(raw).trim()
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  return `https://${value}`
}

export function getRecordId(rowOriginal) {
  const rawId = rowOriginal?.id
  if (rawId === undefined || rawId === null) return null
  return String(rawId)
}

export function normalizeJiraKey(raw) {
  if (raw == null) return null
  const key = String(raw).trim().toUpperCase()
  return /^[A-Z0-9]+-\d+$/.test(key) ? key : null
}

export function buildJiraBrowseUrl(jiraKey) {
  const key = normalizeJiraKey(jiraKey)
  return key ? `https://jira.apple.net/browse/${key}` : null
}

export function normalizeComment(raw) {
  if (typeof raw === "string") return raw
  if (raw == null) return ""
  return String(raw)
}

export function normalizeNeedToSend(raw) {
  if (typeof raw === "boolean") return raw
  if (raw === null || raw === undefined) return false
  if (typeof raw === "number" && Number.isFinite(raw)) return raw === 1
  if (typeof raw === "string") {
    const normalized = raw.trim().toLowerCase()
    if (!normalized) return false
    if (["1", "true", "t", "y", "yes"].includes(normalized)) return true
    if (["0", "false", "f", "n", "no"].includes(normalized)) return false
    const parsed = Number.parseInt(normalized, 10)
    if (Number.isFinite(parsed)) return parsed === 1
    return false
  }
  if (typeof raw === "bigint") return Number(raw) === 1
  return false
}

export function normalizeBinaryFlag(raw) {
  if (typeof raw === "boolean") return raw
  if (raw === null || raw === undefined) return false
  if (typeof raw === "number" && Number.isFinite(raw)) return raw === 1
  if (typeof raw === "string") {
    const normalized = raw.trim().toLowerCase()
    if (!normalized || normalized === ".") return false
    if (["1", "true", "t", "y", "yes"].includes(normalized)) return true
    if (["0", "false", "f", "n", "no"].includes(normalized)) return false
    const numeric = Number(normalized)
    return Number.isFinite(numeric) ? numeric === 1 : false
  }
  if (typeof raw === "bigint") return Number(raw) === 1
  return false
}

export function normalizeStatus(raw) {
  if (raw == null) return null
  return String(raw).trim().toUpperCase().replace(/\s+/g, "_")
}
