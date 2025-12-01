// src/features/line-dashboard/api/line-settings.js
// 라인 조기 알림 설정 CRUD API 래퍼
import { buildBackendUrl } from "@/lib/api"

import {
  normalizeEntry,
  normalizeUserSdwt,
  unwrapErrorMessage,
} from "../utils/line-settings"

async function safeParseJson(response) {
  try {
    return await response.json()
  } catch {
    return {}
  }
}

function buildApiError(response, payload, fallbackMessage) {
  const apiMessage =
    payload && typeof payload === "object" && typeof payload.error === "string"
      ? payload.error
      : ""
  const message = unwrapErrorMessage(apiMessage) || fallbackMessage
  const error = new Error(message)
  error.status = response.status
  return error
}

export async function fetchLineSettings(lineId) {
  if (!lineId) {
    return { entries: [], userSdwtValues: [] }
  }

  const endpoint = buildBackendUrl("/drone-early-inform", { lineId })
  const response = await fetch(endpoint, {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await safeParseJson(response)

  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to load settings (status ${response.status})`,
    )
  }

  const entries = (Array.isArray(payload?.rows) ? payload.rows : [])
    .map((row) => normalizeEntry(row, lineId))
    .filter((row) => row !== null)
  const userSdwtValues = normalizeUserSdwt(payload?.userSdwt)

  return { entries, userSdwtValues }
}

export async function createLineSetting({ lineId, mainStep, customEndStep }) {
  const endpoint = buildBackendUrl("/drone-early-inform")
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      lineId,
      mainStep,
      customEndStep: customEndStep ?? null,
    }),
  })

  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to create entry (status ${response.status})`,
    )
  }

  const entry = normalizeEntry(payload?.entry, lineId)
  return { entry }
}

export async function updateLineSetting({ id, lineId, mainStep, customEndStep }) {
  const endpoint = buildBackendUrl("/drone-early-inform")
  const response = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      id: Number.parseInt(id, 10),
      ...(mainStep !== undefined ? { mainStep } : {}),
      ...(customEndStep !== undefined ? { customEndStep } : {}),
    }),
  })

  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to update entry (status ${response.status})`,
    )
  }

  const entry = normalizeEntry(payload?.entry, lineId)
  return { entry }
}

export async function deleteLineSetting({ id }) {
  const endpoint = buildBackendUrl("/drone-early-inform", { id })
  const response = await fetch(endpoint, {
    method: "DELETE",
    credentials: "include",
  })

  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(
      response,
      payload,
      `Failed to delete entry (status ${response.status})`,
    )
  }

  return { ok: true }
}
