export function buildLogRangeSearch(currentSearch, logQueryOptions) {
  const nextParams = new URLSearchParams(currentSearch)
  let hasChanged = false

  for (const [key, value] of Object.entries(logQueryOptions || {})) {
    if (nextParams.get(key) !== value) {
      nextParams.set(key, value)
      hasChanged = true
    }
  }

  return hasChanged ? `?${nextParams.toString()}` : null
}

export function getObserverEquipmentPath(eqpId) {
  const normalizedEqpId = String(eqpId || "").trim()
  return normalizedEqpId ? `/observer/${normalizedEqpId}` : "/observer"
}

export function isObserverEquipmentPath(pathname) {
  const segments = String(pathname || "").split("/").filter(Boolean)
  return segments[0] === "observer" && segments.length > 1
}
