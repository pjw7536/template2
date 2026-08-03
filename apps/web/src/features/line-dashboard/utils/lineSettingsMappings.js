export function normalizeMappingOptionValue(value) {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim()
}

export function findMappingDefaultOption(values, preferredValue) {
  const options = Array.isArray(values) ? values : []
  if (options.length === 0) return ""
  const normalizedPreferred = String(preferredValue || "").trim().toLowerCase()
  if (normalizedPreferred) {
    const matched = options.find((value) => (
      typeof value === "string" && value.trim().toLowerCase() === normalizedPreferred
    ))
    if (matched) return matched
  }
  return options[0] || ""
}

export function buildMappingOptionsFromValues(values) {
  const normalizedValues = Array.isArray(values)
    ? values.map(normalizeMappingOptionValue).filter(Boolean)
    : []
  const uniqueValues = Array.from(new Set(normalizedValues))
  return { userSdwtProds: uniqueValues, sdwtProds: uniqueValues }
}

export function buildMappingLineOptions({ lineRows, currentLineId, currentValues }) {
  const currentLine = normalizeMappingOptionValue(currentLineId)
  const normalizedCurrentLineId = currentLine.toLowerCase()
  const currentOption = currentLine
    ? {
        lineId: currentLine,
        values: buildMappingOptionsFromValues(currentValues).userSdwtProds,
      }
    : null
  const otherOptions = (Array.isArray(lineRows) ? lineRows : [])
    .map((row) => {
      const rowLineId = normalizeMappingOptionValue(row?.lineId)
      if (!rowLineId || rowLineId.toLowerCase() === normalizedCurrentLineId) return null
      const values = buildMappingOptionsFromValues(row?.userSdwtProds).userSdwtProds
      return values.length > 0 ? { lineId: rowLineId, values } : null
    })
    .filter(Boolean)
    .sort((a, b) => a.lineId.localeCompare(b.lineId))

  return currentOption ? [currentOption, ...otherOptions] : otherOptions
}

export function getMappingLineOptionValues(lineOptions, selectedLineId) {
  const normalizedSelectedLineId = normalizeMappingOptionValue(selectedLineId)
  const option = (Array.isArray(lineOptions) ? lineOptions : []).find((row) => (
    normalizeMappingOptionValue(row?.lineId).toLowerCase() === normalizedSelectedLineId.toLowerCase()
  ))
  return Array.isArray(option?.values) ? option.values : []
}

export function buildMappingValueLineLabels(lineRows, currentLineId) {
  const normalizedCurrentLineId = normalizeMappingOptionValue(currentLineId).toLowerCase()
  const labels = {}

  if (!Array.isArray(lineRows)) return labels

  lineRows.forEach((row) => {
    const rowLineId = normalizeMappingOptionValue(row?.lineId)
    const values = Array.isArray(row?.userSdwtProds) ? row.userSdwtProds : []
    values.forEach((value) => {
      const normalizedValue = normalizeMappingOptionValue(value)
      if (!rowLineId || !normalizedValue) return
      const key = normalizedValue.toLowerCase()
      if (rowLineId.toLowerCase() !== normalizedCurrentLineId) {
        labels[key] = rowLineId
      }
    })
  })

  return labels
}

export function buildTargetMappingKey({ userSdwtProd, sdwtProd }) {
  return `${String(userSdwtProd || "").trim().toLowerCase()}::${String(sdwtProd || "").trim().toLowerCase()}`
}

export function findMatchingUserSdwtValue(values, preferredValue) {
  const normalizedPreferred = String(preferredValue || "").trim().toLowerCase()
  if (!normalizedPreferred) return ""
  return (Array.isArray(values) ? values : []).find((value) => (
    String(value || "").trim().toLowerCase() === normalizedPreferred
  )) || ""
}

export function parseRecipientSearchTerms(value) {
  return String(value || "")
    .split(/[,，]/)
    .map((term) => term.trim())
    .filter(Boolean)
}
