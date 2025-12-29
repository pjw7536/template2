const TEAM_SWITCHER_STORAGE_KEY = "app:team-switcher:last-selection"

export function normalizeTeamId(value) {
  if (value === null || value === undefined) return null
  const normalized = typeof value === "string" ? value.trim() : String(value).trim()
  return normalized ? normalized : null
}

export function normalizeTeamOption(option) {
  if (!option || typeof option !== "object") return null

  const id = normalizeTeamId(option.id)
  if (!id) return null

  const label =
    typeof option.label === "string" && option.label.trim()
      ? option.label.trim()
      : id
  const description = typeof option.description === "string" ? option.description : ""
  const lineId = normalizeTeamId(option.lineId)
  const userSdwtProd =
    typeof option.userSdwtProd === "string" ? option.userSdwtProd.trim() : ""

  return { id, label, description, lineId, userSdwtProd }
}

export function isSameTeamOption(a, b) {
  if (!a || !b) return false
  return (
    a.id === b.id &&
    a.label === b.label &&
    a.description === b.description &&
    a.lineId === b.lineId &&
    a.userSdwtProd === b.userSdwtProd
  )
}

export function readStoredTeamOption() {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(TEAM_SWITCHER_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return normalizeTeamOption(parsed)
  } catch {
    return null
  }
}

export function writeStoredTeamOption(option) {
  if (typeof window === "undefined") return
  const normalized = normalizeTeamOption(option)
  if (!normalized) return

  try {
    window.localStorage.setItem(TEAM_SWITCHER_STORAGE_KEY, JSON.stringify(normalized))
  } catch {
    return null
  }
}

export function getStoredLineId() {
  const stored = readStoredTeamOption()
  if (!stored) return null
  return normalizeTeamId(stored.lineId) ?? normalizeTeamId(stored.id)
}

export function getStoredMailboxId() {
  const stored = readStoredTeamOption()
  if (!stored) return null
  return normalizeTeamId(stored.userSdwtProd) ?? normalizeTeamId(stored.id)
}
