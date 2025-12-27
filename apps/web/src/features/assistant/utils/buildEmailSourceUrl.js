function normalizeValue(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function buildEmailSourceUrl(emailId, userSdwtProd) {
  const normalizedEmailId = normalizeValue(emailId)
  if (!normalizedEmailId) return "/emails/inbox"

  const mailbox = normalizeValue(userSdwtProd)
  const params = new URLSearchParams()

  if (mailbox) {
    params.set("user_sdwt_prod", mailbox)
  }

  params.set("emailId", normalizedEmailId)
  if (mailbox) {
    return `/emails/inbox?${params.toString()}`
  }
  return `/emails/sent?${params.toString()}`
}
