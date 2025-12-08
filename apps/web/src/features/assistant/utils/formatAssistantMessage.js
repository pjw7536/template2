import DOMPurify from "dompurify"
import { marked } from "marked"

const markedOptions = {
  breaks: true,
  gfm: true,
  headerIds: false,
  mangle: false,
}

export function formatAssistantMessage(content) {
  if (!content || typeof content !== "string") return ""

  const rawHtml = marked.parse(content, markedOptions)
  return DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } })
}
