function normalizeValue(value) {
  return typeof value === "string" ? value.trim() : ""
}

export function buildEmailSourceUrl(emailId, userSdwtProd) {
  const normalizedEmailId = normalizeValue(emailId)
  if (!normalizedEmailId) return "/emails"

  const mailbox = normalizeValue(userSdwtProd)
  const params = new URLSearchParams()

  if (mailbox) {
    params.set("user_sdwt_prod", mailbox)
  }

  params.set("emailId", normalizedEmailId)
  return `/emails?${params.toString()}`
}

