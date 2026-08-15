import DOMPurify from "dompurify"
import { marked } from "marked"

import { buildEmailSourceUrl } from "./buildEmailSourceUrl"

const markedOptions = {
  breaks: true,
  gfm: true,
  headerIds: false,
  mangle: false,
}

const EMAIL_SOURCE_FALLBACK_LABEL = "관련 메일 보기"

function truncateLabel(value, maxLength = 48) {
  if (typeof value !== "string") return ""
  const trimmed = value.trim()
  if (!trimmed) return ""
  if (trimmed.length <= maxLength) return trimmed
  return `${trimmed.slice(0, maxLength - 1)}…`
}

function isAlphaNumeric(char) {
  if (!char || typeof char !== "string") return false
  return /[0-9A-Za-z]/.test(char)
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function buildSourceLookup(rawSources) {
  const sources = Array.isArray(rawSources) ? rawSources : []
  const lookup = new Map()

  sources.forEach((source) => {
    if (!source || typeof source !== "object") return
    const docId = typeof source.docId === "string" ? source.docId.trim() : ""
    if (!docId) return
    const title = typeof source.title === "string" ? source.title.trim() : ""
    const label = truncateLabel(title) || EMAIL_SOURCE_FALLBACK_LABEL
    lookup.set(docId, { docId, label })
  })

  return lookup
}

function collectTextNodes(node, out) {
  if (!node) return

  if (node.nodeType === 3) {
    out.push(node)
    return
  }

  const children = node.childNodes
  if (!children || children.length === 0) return

  children.forEach((child) => collectTextNodes(child, out))
}

function buildMatches(text, docId) {
  const matches = []
  if (!text || typeof text !== "string") return matches
  if (!docId || typeof docId !== "string") return matches

  const escapedDocId = escapeRegex(docId)

  const addRegexMatches = (regex) => {
    let match
    while ((match = regex.exec(text))) {
      matches.push({ start: match.index, end: match.index + match[0].length, docId })
    }
  }

  const scopedEmailRoute = `\\/emails\\/(?:inbox|sent)\\?[^\\s)]*emailId=${escapedDocId}[^\\s)]*`
  addRegexMatches(new RegExp(`https?:\\/\\/[^\\s)]+${scopedEmailRoute}`, "g"))
  addRegexMatches(new RegExp(scopedEmailRoute, "g"))
  addRegexMatches(new RegExp(`\\/emails\\?[^\\s)]*emailId=${escapedDocId}[^\\s)]*`, "g"))
  addRegexMatches(new RegExp(`emailId\\s*[:=]\\s*${escapedDocId}`, "g"))

  let searchIndex = 0
  while (searchIndex < text.length) {
    const index = text.indexOf(docId, searchIndex)
    if (index === -1) break
    const before = index > 0 ? text[index - 1] : ""
    const after = index + docId.length < text.length ? text[index + docId.length] : ""

    if (!isAlphaNumeric(before) && !isAlphaNumeric(after)) {
      matches.push({ start: index, end: index + docId.length, docId })
    }

    searchIndex = index + docId.length
  }

  return matches
}

function buildReplacementFragment(doc, text, sourceLookup, mailbox, availableMailboxes) {
  const docIds = Array.from(sourceLookup.keys())
  if (docIds.length === 0) return null

  const matches = docIds.flatMap((docId) => buildMatches(text, docId))
  if (matches.length === 0) return null

  matches.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start
    return b.end - b.start - (a.end - a.start)
  })

  const selected = []
  let cursor = 0
  matches.forEach((match) => {
    if (match.start < cursor) return
    selected.push(match)
    cursor = match.end
  })

  if (selected.length === 0) return null

  const fragment = doc.createDocumentFragment()
  let lastIndex = 0
  selected.forEach((match) => {
    if (match.start > lastIndex) {
      fragment.appendChild(doc.createTextNode(text.slice(lastIndex, match.start)))
    }

    const source = sourceLookup.get(match.docId)
    const label = source?.label || match.docId
    const anchor = doc.createElement("a")
    anchor.setAttribute(
      "href",
      buildEmailSourceUrl(match.docId, mailbox, { availableMailboxes }),
    )
    anchor.setAttribute("data-email-source", "true")
    anchor.textContent = label
    fragment.appendChild(anchor)

    lastIndex = match.end
  })

  if (lastIndex < text.length) {
    fragment.appendChild(doc.createTextNode(text.slice(lastIndex)))
  }

  return fragment
}

function getEmailSourceFromHref(href, sourceLookup) {
  if (!href || typeof href !== "string") return null

  try {
    const url = new URL(href, "http://assistant.local")
    if (!/^\/emails(?:\/(?:inbox|sent))?\/?$/.test(url.pathname)) return null

    const docId = url.searchParams.get("emailId")?.trim()
    if (!docId) return null

    return (
      sourceLookup.get(docId) || {
        docId,
        label: EMAIL_SOURCE_FALLBACK_LABEL,
      }
    )
  } catch {
    return null
  }
}

function replaceEmailLinkLabels(container, sourceLookup) {
  container.querySelectorAll("a[href]").forEach((anchor) => {
    const source = getEmailSourceFromHref(anchor.getAttribute("href"), sourceLookup)
    if (!source) return

    anchor.setAttribute("data-email-source", "true")
    anchor.textContent = source.label
  })
}

function injectEmailSourceLinks(rawHtml, sources, mailbox, availableMailboxes) {
  const sourceLookup = buildSourceLookup(sources)

  if (typeof window === "undefined") return rawHtml
  if (typeof DOMParser === "undefined") return rawHtml

  const parser = new DOMParser()
  const doc = parser.parseFromString(rawHtml, "text/html")
  const container = doc.body
  if (!container) return rawHtml

  replaceEmailLinkLabels(container, sourceLookup)

  const textNodes = []
  collectTextNodes(container, textNodes)

  textNodes.forEach((node) => {
    const text = node?.nodeValue
    if (!text || typeof text !== "string") return

    const parentElement = node.parentElement
    if (parentElement?.closest?.("a")) return

    const fragment = buildReplacementFragment(doc, text, sourceLookup, mailbox, availableMailboxes)
    if (!fragment) return

    node.parentNode?.replaceChild(fragment, node)
  })

  return container.innerHTML
}

function applyLinkTargetAttributes(rawHtml) {
  if (typeof DOMParser === "undefined") return rawHtml

  const parser = new DOMParser()
  const doc = parser.parseFromString(rawHtml, "text/html")
  const container = doc.body
  if (!container) return rawHtml

  container.querySelectorAll("a[href]").forEach((anchor) => {
    if (anchor.hasAttribute("data-email-source")) {
      anchor.removeAttribute("target")
      anchor.removeAttribute("rel")
      return
    }
    anchor.setAttribute("target", "_blank")
    anchor.setAttribute("rel", "noopener noreferrer")
  })

  return container.innerHTML
}

export function formatAssistantMessage(content, sources = [], mailbox = "", availableMailboxes = []) {
  if (!content || typeof content !== "string") return ""

  const rawHtml = marked.parse(content, markedOptions)
  const htmlWithSources = injectEmailSourceLinks(rawHtml, sources, mailbox, availableMailboxes)
  const htmlWithLinkTargets = applyLinkTargetAttributes(htmlWithSources)
  return DOMPurify.sanitize(htmlWithLinkTargets, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["data-email-source", "target", "rel"],
  })
}
