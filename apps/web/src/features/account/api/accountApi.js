import { buildBackendUrl } from "@/lib/api"

const endpoints = {
  affiliation: "/api/v1/account/affiliation",
  grants: "/api/v1/account/access/grants",
  manageable: "/api/v1/account/access/manageable",
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
