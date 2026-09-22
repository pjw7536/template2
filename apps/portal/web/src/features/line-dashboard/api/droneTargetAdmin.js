// 파일 경로: src/features/line-dashboard/api/droneTargetAdmin.js
// Line Dashboard 관리자 전용 drone_sop_target 관리 API 래퍼입니다.
import { buildBackendUrl, safeParseJson } from "@/lib/api"

import { buildApiError } from "./apiError"
import {
  normalizeDroneTargetAdminCount,
  normalizeDroneTargetAdminRow,
  normalizeDroneTargetAdminRows,
} from "../utils/droneTargetAdmin"

const DRONE_TARGET_ADMIN_PATH = "/api/v1/line-dashboard/admin/drone-targets"

async function parseDroneTargetAdminResponse(response, fallbackMessage) {
  const payload = await safeParseJson(response)
  if (!response.ok) {
    throw buildApiError(response, payload, fallbackMessage)
  }
  return payload
}

export async function fetchDroneTargetAdminRows() {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    cache: "no-store",
    credentials: "include",
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to load drone targets (status ${response.status})`,
  )

  return {
    targets: normalizeDroneTargetAdminRows(payload?.targets),
    rowCount: normalizeDroneTargetAdminCount(payload?.rowCount),
  }
}

export async function createDroneTargetAdminRow({ lineId, targetUserSdwtProd }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ lineId, targetUserSdwtProd }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to create drone target (status ${response.status})`,
  )

  return {
    target: normalizeDroneTargetAdminRow(payload?.target),
    created: Boolean(payload?.created),
  }
}

export async function updateDroneTargetAdminRow({ id, lineId, targetUserSdwtProd }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ id, lineId, targetUserSdwtProd }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to update drone target (status ${response.status})`,
  )

  return {
    target: normalizeDroneTargetAdminRow(payload?.target),
    updated: Boolean(payload?.updated),
  }
}

export async function deleteDroneTargetAdminRow({ id }) {
  const response = await fetch(buildBackendUrl(DRONE_TARGET_ADMIN_PATH), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ id }),
  })
  const payload = await parseDroneTargetAdminResponse(
    response,
    `Failed to delete drone target (status ${response.status})`,
  )

  return {
    deleted: Boolean(payload?.deleted),
    target: normalizeDroneTargetAdminRow(payload?.target),
  }
}
