function normalizeText(value) {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeNumber(value) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
}

export function normalizeDroneTargetAdminRow(rawTarget) {
  if (!rawTarget || typeof rawTarget !== "object") return null
  const id = Number.parseInt(rawTarget.id, 10)
  if (!Number.isFinite(id) || id <= 0) return null

  return {
    id,
    lineId: normalizeText(rawTarget.lineId),
    targetUserSdwtProd: normalizeText(rawTarget.targetUserSdwtProd),
    mappingCount: normalizeNumber(rawTarget.mappingCount),
    recipientCount: normalizeNumber(rawTarget.recipientCount),
    channelConfigCount: normalizeNumber(rawTarget.channelConfigCount),
    dispatchCount: normalizeNumber(rawTarget.dispatchCount),
    hasNeedToSendRule: Boolean(rawTarget.hasNeedToSendRule),
    createdAt: normalizeText(rawTarget.createdAt),
    updatedAt: normalizeText(rawTarget.updatedAt),
  }
}

export function normalizeDroneTargetAdminRows(values) {
  return (Array.isArray(values) ? values : [])
    .map((target) => normalizeDroneTargetAdminRow(target))
    .filter(Boolean)
}

export function normalizeDroneTargetAdminCount(value) {
  return normalizeNumber(value)
}
