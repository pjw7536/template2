import { buildBackendUrl } from "@/lib/api"

import { buildEmailListSearchParams } from "../utils/filters"

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
      typeof data?.message === "string"
        ? data.message
        : `요청이 실패했습니다. (status ${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.payload = data
    throw error
  }

  return data
}

export async function fetchInboxEmails(params = {}) {
  const searchParams = buildEmailListSearchParams(params)

  const response = await fetch(buildBackendUrl(`${BASE_PATH}/inbox/`, searchParams), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchSentEmails(params = {}) {
  const searchParams = buildEmailListSearchParams(params, { includeMailbox: false })

  const response = await fetch(buildBackendUrl(`${BASE_PATH}/sent/`, searchParams), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmails(params = {}) {
  return fetchInboxEmails(params)
}

export async function fetchEmailMailboxes() {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mailboxes/`), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxSummary() {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/mailboxes/summary/`), {
    credentials: "include",
  })

  return handleJsonResponse(response)
}

export async function fetchEmailMailboxMembers(userSdwtProd) {
  const trimmed = typeof userSdwtProd === "string" ? userSdwtProd.trim() : ""
  const response = await fetch(
    buildBackendUrl(`${BASE_PATH}/mailboxes/members/`, {
      userSdwtProd: trimmed,
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
    body: JSON.stringify({ emailIds }),
  })
  return handleJsonResponse(response)
}

export async function moveEmails(emailIds = [], toUserSdwtProd = "") {
  const response = await fetch(buildBackendUrl(`${BASE_PATH}/move/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({ emailIds, toUserSdwtProd }),
  })
  return handleJsonResponse(response)
}
