export function normalizeMailbox(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function getMailboxFromSearchParams(searchParams) {
  if (!searchParams) return ""

  return normalizeMailbox(
    searchParams.get("mailbox") ||
      searchParams.get("userSdwtProd") ||
      searchParams.get("user_sdwt_prod") ||
      "",
  )
}

export function buildMailboxUrl(mailbox) {
  const trimmed = normalizeMailbox(mailbox)
  if (!trimmed) return "/emails"
  return `/emails?mailbox=${encodeURIComponent(trimmed)}`
}

export function buildMembersUrl(mailbox) {
  const trimmed = normalizeMailbox(mailbox)
  if (!trimmed) return "/emails/members"
  return `/emails/members?mailbox=${encodeURIComponent(trimmed)}`
}

