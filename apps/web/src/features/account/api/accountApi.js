import { buildBackendUrl } from "@/lib/api"

const endpoints = {
  overview: "/api/v1/account/overview",
  affiliation: "/api/v1/account/affiliation",
  affiliationRequests: "/api/v1/account/affiliation/requests",
  affiliationApprove: "/api/v1/account/affiliation/approve",
  grants: "/api/v1/account/access/grants",
  manageable: "/api/v1/account/access/manageable",
  mailboxMembers: "/api/v1/emails/mailboxes/members/",
}

async function request(url, options = {}) {
  try {
    const response = await fetch(url, {
      credentials: "include",
      ...options,
    })
    const contentType = response.headers.get("content-type") || ""
    let data = null
    if (contentType.includes("application/json")) {
      try {
        data = await response.json()
      } catch {
        data = null
      }
    } else {
      const text = await response.text()
      try {
        data = text ? JSON.parse(text) : null
      } catch {
        data = text || null
      }
    }

    return { ok: response.ok, data }
  } catch (error) {
    return { ok: false, data: { error: String(error) } }
  }
}

async function unwrap(response, defaultMessage) {
  if (response.ok) return response.data
  const message = (response?.data && response.data.error) || defaultMessage
  throw new Error(message || "Request failed")
}

export const accountApi = {
  async fetchAffiliation() {
    const url = buildBackendUrl(endpoints.affiliation)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation")
  },

  async fetchOverview() {
    const url = buildBackendUrl(endpoints.overview)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load account overview")
  },

  async updateAffiliation(payload) {
    const url = buildBackendUrl(endpoints.affiliation)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update affiliation")
  },

  async fetchManageableGroups() {
    const url = buildBackendUrl(endpoints.manageable)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load group members")
  },

  async fetchAffiliationRequests({
    page = 1,
    pageSize = 20,
    status = "pending",
    search = "",
    userSdwtProd = "",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("page_size", String(pageSize))
    if (status) params.set("status", status)
    if (search) params.set("q", search)
    if (userSdwtProd) params.set("user_sdwt_prod", userSdwtProd)

    const url = buildBackendUrl(`${endpoints.affiliationRequests}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation requests")
  },

  async fetchMailboxMembers({ userSdwtProd } = {}) {
    if (!userSdwtProd) {
      return { userSdwtProd: "", members: [] }
    }
    const params = new URLSearchParams()
    params.set("user_sdwt_prod", userSdwtProd)
    const url = buildBackendUrl(`${endpoints.mailboxMembers}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load mailbox members")
  },

  async decideAffiliationRequest(payload) {
    const url = buildBackendUrl(endpoints.affiliationApprove)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update affiliation request")
  },

  async updateGrant(payload) {
    const url = buildBackendUrl(endpoints.grants)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update grant")
  },
}
