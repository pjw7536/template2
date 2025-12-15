export function formatEmailDate(value) {
  if (!value) return ""
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

