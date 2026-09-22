import {
  isSentMailbox,
  isUnassignedMailbox,
  normalizeMailbox,
} from "./mailbox"

export const EMAIL_LIST_MIN_WIDTH = 600
export const EMAIL_DETAIL_MIN_WIDTH = 420
export const EMAIL_SPLIT_GAP_PX = 16

export function parseRoutedEmailId(value) {
  const normalized = typeof value === "string" ? value.trim() : ""
  if (!normalized) return null

  const numericValue = /^\d+$/.test(normalized) ? Number(normalized) : null
  if (Number.isSafeInteger(numericValue) && numericValue > 0) return numericValue

  const ragMatch = normalized.match(/^email-(\d+)$/i)
  if (!ragMatch) return null

  const ragEmailId = Number(ragMatch[1])
  return Number.isSafeInteger(ragEmailId) && ragEmailId > 0 ? ragEmailId : null
}

export function clampEmailListWidth(nextWidth, container) {
  if (!container) return nextWidth
  const { width } = container.getBoundingClientRect()
  if (!width) return nextWidth

  const maxWidth = Math.max(
    EMAIL_LIST_MIN_WIDTH,
    width - EMAIL_SPLIT_GAP_PX - EMAIL_DETAIL_MIN_WIDTH,
  )
  return Math.min(Math.max(nextWidth, EMAIL_LIST_MIN_WIDTH), maxWidth)
}

export function buildEmailMoveTargets(mailboxes, activeMailbox) {
  const normalizedActive = normalizeMailbox(activeMailbox)
  const options = (Array.isArray(mailboxes) ? mailboxes : [])
    .map(normalizeMailbox)
    .filter(Boolean)
    .filter((mailbox) => !isSentMailbox(mailbox) && !isUnassignedMailbox(mailbox))
    .filter((mailbox) => mailbox !== normalizedActive)

  return Array.from(new Set(options)).map((mailbox) => ({ value: mailbox, label: mailbox }))
}
