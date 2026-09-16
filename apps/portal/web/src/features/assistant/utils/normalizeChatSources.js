export function normalizeChatSources(rawSources) {
  if (!Array.isArray(rawSources)) return []

  return rawSources
    .map((item) => {
      if (!item || typeof item !== "object") return null
      const docId =
        (typeof item.docId === "string" && item.docId.trim()) ||
        (typeof item.doc_id === "string" && item.doc_id.trim())
      if (!docId) return null
      const title = typeof item.title === "string" ? item.title.trim() : ""
      const snippet = typeof item.snippet === "string" ? item.snippet.trim() : ""
      return { docId, title, snippet }
    })
    .filter(Boolean)
}
