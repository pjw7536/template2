import { buildBackendUrl } from "@/lib/api"

const BASE_PATH = "/api/v1/emails"

async function handleJsonResponse(response) {
  let data = {}
  try {
    data = await response.json()
  } catch {
    // ignore
  }

  if (!response.ok) {
    const message =
      typeof data?.error === "string"
        ? data.error
        : `요청이 실패했습니다. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = data
    throw error
  }

  return data
}

export async function fetchEmails(params = {}) {
  const searchParams = {}
  if (params.page) searchParams.page = params.page
  if (params.pageSize) searchParams.page_size = params.pageSize
  if (params.userSdwtProd) searchParams.user_sdwt_prod = params.userSdwtProd
  if (params.q) searchParams.q = params.q
  if (params.sender) searchParams.sender = params.sender
  if (params.recipient) searchParams.recipient = params.recipient
  if (params.dateFrom) searchParams.date_from = params.dateFrom
  if (params.dateTo) searchParams.date_to = params.dateTo

  const response = await fetch(buildBackendUrl(`${BASE_PATH}/`, searchParams), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxes() {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mailboxes/`), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxMembers(userSdwtProd) {
  const trimmed = typeof userSdwtProd === "string" ? userSdwtProd.trim() : ""
  const response = await fetch(
    buildBackendUrl(`${BASE_PATH}/mailboxes/members/`, {
      user_sdwt_prod: trimmed,
    }),
    { credentials: "include" },
  )

  return handleJsonResponse(response)
}

export async function fetchEmail(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/`), {
    credentials: "include",
  })
  return handleJsonResponse(response)
}

export async function fetchEmailHtml(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/html/`), {
    credentials: "include",
  })

  if (response.status === 204) return ""
  if (!response.ok) {
    const message = `HTML 본문을 불러오지 못했습니다. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  return response.text()
}

export async function deleteEmail(emailId) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/${emailId}/`), {
    method: "DELETE",
    credentials: "include",
  })
  return handleJsonResponse(response)
}

export async function bulkDeleteEmails(emailIds = []) {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/bulk-delete/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ email_ids: emailIds }),
  })
  return handleJsonResponse(response)
}
