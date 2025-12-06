// src/features/voc/utils.js
// VOC 화면 전용 헬퍼
import DOMPurify from "dompurify"

const IMAGE_MARKDOWN_PATTERN = /!\[([^\]]*)\]\((data:image\/[^)]+)\)/g
const HTML_TAG_PATTERN = /<\/?[a-z][\s\S]*>/i

export function createId() {
  return `voc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function formatTimestamp(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "기록 없음"
  return date.toLocaleString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function escapeHtml(value = "") {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
}

function parseContentSegments(content) {
  if (!content) return []
  const segments = []
  let lastIndex = 0
  let match

  while ((match = IMAGE_MARKDOWN_PATTERN.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", value: content.slice(lastIndex, match.index) })
    }
    segments.push({ type: "image", alt: match[1], src: match[2] })
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < content.length) {
    segments.push({ type: "text", value: content.slice(lastIndex) })
  }

  return segments.length > 0 ? segments : [{ type: "text", value: content }]
}

function segmentsToHtml(segments) {
  return segments
    .map((segment) => {
      if (segment.type === "image") {
        const alt = escapeHtml(segment.alt || "첨부 이미지")
        return `<p><img src="${segment.src}" alt="${alt}" loading="lazy" /></p>`
      }
      const safeText = escapeHtml(segment.value || "")
      const withBreaks = safeText.replace(/\n/g, "<br />")
      return `<p>${withBreaks}</p>`
    })
    .join("")
}

export function sanitizeContentHtml(content) {
  if (!content) return ""
  const trimmed = typeof content === "string" ? content : ""
  const baseHtml = HTML_TAG_PATTERN.test(trimmed)
    ? trimmed
    : segmentsToHtml(parseContentSegments(trimmed))

  return DOMPurify.sanitize(baseHtml, {
    ADD_ATTR: ["style", "loading"],
  })
}

export function hasMeaningfulContent(content, { skipSanitize = false } = {}) {
  const safeHtml = skipSanitize ? (content || "") : sanitizeContentHtml(content)
  if (!safeHtml) return false

  const hasImage = /<img\b[^>]*src=["']?[^"'>\s]+/i.test(safeHtml)
  const textOnly = safeHtml
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, "")
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/<img\b[^>]*>/gi, " ")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .trim()

  return Boolean(hasImage || textOnly)
}
