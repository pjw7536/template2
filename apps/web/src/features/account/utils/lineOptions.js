export function buildLineSwitcherOptions(lineOptions) {
  return (Array.isArray(lineOptions) ? lineOptions : [])
    .map((lineId) => (typeof lineId === "string" ? lineId.trim() : ""))
    .filter(Boolean)
    .map((lineId) => ({ id: lineId, label: lineId, lineId }))
}
