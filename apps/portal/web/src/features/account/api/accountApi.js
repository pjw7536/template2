import { buildBackendUrl } from "@/lib/api"

const endpoints = {
  overview: "/api/v1/account/overview",
  affiliation: "/api/v1/account/affiliation",
  affiliationRequests: "/api/v1/account/affiliation/requests",
  affiliationApprove: "/api/v1/account/affiliation/approve",
  affiliationMembers: "/api/v1/account/affiliation/members",
  affiliationAccess: "/api/v1/account/affiliation/access",
  accessRequest: "/api/v1/account/access/request",
  accessUsers: "/api/v1/account/access/users",
  pendingAccessRequests: "/api/v1/account/access/pending-requests",
  pendingAccessRequestsBulkApprove: "/api/v1/account/access/pending-requests/bulk-approve",
  accessMatrix: "/api/v1/account/access/matrix",
  accessPolicyRules: "/api/v1/account/access/policy-rules",
  accessPolicyRulesBulkApply: "/api/v1/account/access/policy-rules/bulk-apply",
  accessAuditLogs: "/api/v1/account/access/audit-logs",
  users: "/api/v1/account/users",
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
    return { ok: false, data: { message: String(error) } }
  }
}

async function unwrap(response, defaultMessage) {
  if (response.ok) return response.data
  const message = (response?.data && response.data.message) || defaultMessage
  throw new Error(message || "Request failed")
}

function normalizeUser(rawUser) {
  if (!rawUser || typeof rawUser !== "object") return null
  if (!["user", "external"].includes(rawUser.recipientType)) return null
  const recipientType = rawUser.recipientType
  const userId = Number.parseInt(rawUser.userId, 10)
  const knoxId = typeof rawUser.knoxId === "string" ? rawUser.knoxId : ""
  const externalKnoxId = typeof rawUser.externalKnoxId === "string" ? rawUser.externalKnoxId : ""
  if (recipientType === "user" && (!Number.isFinite(userId) || userId <= 0)) return null
  if (recipientType === "external" && !externalKnoxId) return null
  const recipientKey = typeof rawUser.recipientKey === "string" ? rawUser.recipientKey.trim() : ""
  if (!recipientKey) return null

  return {
    id: recipientType === "external" ? recipientKey : userId,
    userId: recipientType === "external" ? null : userId,
    recipientType,
    recipientKey,
    externalKnoxId,
    username: typeof rawUser.username === "string" ? rawUser.username : "",
    displayName: typeof rawUser.displayName === "string" ? rawUser.displayName : "",
    sabun: typeof rawUser.sabun === "string" ? rawUser.sabun : "",
    knoxId,
    email: typeof rawUser.email === "string" ? rawUser.email : "",
    department: typeof rawUser.department === "string" ? rawUser.department : "",
    line: typeof rawUser.line === "string" ? rawUser.line : "",
    userSdwtProd: typeof rawUser.userSdwtProd === "string" ? rawUser.userSdwtProd : "",
  }
}

function normalizeUsers(values) {
  return (Array.isArray(values) ? values : []).map(normalizeUser).filter(Boolean)
}

function normalizeTextValues(values) {
  return Array.isArray(values)
    ? values.filter((value) => typeof value === "string" && value.trim())
    : []
}

export async function fetchAccountUserPool({
  search = "",
  department = "",
  userSdwtProd = "",
  contactField = "",
  limit = 50,
  includeExternalSnapshots = false,
} = {}) {
  const params = new URLSearchParams()
  if (search) params.set("search", search)
  if (department) params.set("department", department)
  if (userSdwtProd) params.set("userSdwtProd", userSdwtProd)
  if (contactField) params.set("contactField", contactField)
  if (includeExternalSnapshots) params.set("includeExternalSnapshots", "true")
  params.set("limit", String(limit))

  const url = buildBackendUrl(`${endpoints.users}?${params.toString()}`)
  const response = await request(url, { cache: "no-store" })
  const payload = await unwrap(response, "Failed to load account users")
  return {
    results: normalizeUsers(payload?.results),
    departments: normalizeTextValues(payload?.departments),
    userSdwtProds: normalizeTextValues(payload?.userSdwtProds),
  }
}

export const accountApi = {
  fetchUserPool: fetchAccountUserPool,

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

  async updateAffiliation({ userSdwtProd }) {
    const url = buildBackendUrl(endpoints.affiliation)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userSdwtProd }),
    })
    return unwrap(response, "Failed to update affiliation")
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
    params.set("pageSize", String(pageSize))
    if (status) params.set("status", status)
    if (search) params.set("search", search)
    if (userSdwtProd) params.set("userSdwtProd", userSdwtProd)

    const url = buildBackendUrl(`${endpoints.affiliationRequests}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation requests")
  },

  async fetchAffiliationMembers({ userSdwtProd } = {}) {
    if (!userSdwtProd) {
      return { userSdwtProd: "", members: [] }
    }
    const params = new URLSearchParams()
    params.set("userSdwtProd", userSdwtProd)
    const url = buildBackendUrl(`${endpoints.affiliationMembers}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load affiliation members")
  },

  async decideAffiliationRequest({ changeId, decision, rejectionReason }) {
    const url = buildBackendUrl(endpoints.affiliationApprove)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        changeId,
        decision,
        ...(rejectionReason ? { rejectionReason } : {}),
      }),
    })
    return unwrap(response, "Failed to update affiliation request")
  },

  async grantAffiliationAccess(payload) {
    const url = buildBackendUrl(endpoints.affiliationAccess)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update affiliation access")
  },

  async revokeAffiliationAccess(payload) {
    const url = buildBackendUrl(endpoints.affiliationAccess)
    const response = await request(url, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to revoke affiliation access")
  },

  async requestScopeAccess(scopes) {
    const url = buildBackendUrl(endpoints.accessRequest)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scopes }),
    })
    return unwrap(response, "Failed to request scope access")
  },

  async fetchAccessUsers({
    page = 1,
    pageSize = 20,
    status = "",
    source = "",
    search = "",
    department = "",
    scope = "portal",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("pageSize", String(pageSize))
    if (status) params.set("status", status)
    if (source) params.set("source", source)
    if (search) params.set("search", search)
    if (department) params.set("department", department)
    if (scope) params.set("scope", scope)

    const url = buildBackendUrl(`${endpoints.accessUsers}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access users")
  },

  async fetchAccessMatrix({
    page = 1,
    pageSize = 20,
    search = "",
    department = "",
    manualGrantOnly = false,
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("pageSize", String(pageSize))
    if (search) params.set("search", search)
    if (department) params.set("department", department)
    if (manualGrantOnly) params.set("manualGrantOnly", "true")

    const url = buildBackendUrl(`${endpoints.accessMatrix}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access matrix")
  },

  async fetchPendingAccessRequests({ page = 1, pageSize = 20, scope = "all" } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("pageSize", String(pageSize))
    if (scope && scope !== "all") params.set("scope", scope)

    const url = buildBackendUrl(`${endpoints.pendingAccessRequests}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load pending access requests")
  },

  async bulkApprovePendingAccessRequests({ requestIds }) {
    const url = buildBackendUrl(endpoints.pendingAccessRequestsBulkApprove)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requestIds }),
    })
    return unwrap(response, "Failed to approve pending access requests")
  },

  async decideAccessUser({ userId, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessUsers}/${userId}/decision`)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update access user")
  },

  async fetchUserScopeData({ userId, scope }) {
    const params = new URLSearchParams({ scope })
    const url = buildBackendUrl(
      `${endpoints.accessUsers}/${userId}/data-scope?${params.toString()}`,
    )
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load user data scope")
  },

  async updateUserScopeData({ userId, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessUsers}/${userId}/data-scope`)
    const response = await request(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update user data scope")
  },

  async applyAllAccessUser({ userId, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessUsers}/${userId}/apply-all`)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to apply all access permissions")
  },

  async fetchAccessPolicyRules({ scope = "portal" } = {}) {
    const params = new URLSearchParams()
    if (scope) params.set("scope", scope)
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access policy rules")
  },

  async createAccessPolicyRule(payload) {
    const url = buildBackendUrl(endpoints.accessPolicyRules)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to create access policy rule")
  },

  async bulkApplyAccessPolicyRules(payload) {
    const url = buildBackendUrl(endpoints.accessPolicyRulesBulkApply)
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to apply access policy rules")
  },

  async updateAccessPolicyRule({ id, ...payload }) {
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}/${id}`)
    const response = await request(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    return unwrap(response, "Failed to update access policy rule")
  },

  async deleteAccessPolicyRule({ id }) {
    const url = buildBackendUrl(`${endpoints.accessPolicyRules}/${id}`)
    const response = await request(url, { method: "DELETE" })
    return unwrap(response, "Failed to delete access policy rule")
  },

  async fetchAccessAuditLogs({
    page = 1,
    pageSize = 20,
    scope = "",
    userId = "",
    action = "",
  } = {}) {
    const params = new URLSearchParams()
    params.set("page", String(page))
    params.set("pageSize", String(pageSize))
    if (scope) params.set("scope", scope)
    if (userId) params.set("userId", String(userId))
    if (action) params.set("action", action)

    const url = buildBackendUrl(`${endpoints.accessAuditLogs}?${params.toString()}`)
    const response = await request(url, { cache: "no-store" })
    return unwrap(response, "Failed to load access audit logs")
  },
}
