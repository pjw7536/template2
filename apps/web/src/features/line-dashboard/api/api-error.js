// src/features/line-dashboard/api/api-error.js
import { unwrapErrorMessage } from "../utils/line-settings"

export function buildApiError(response, payload, fallbackMessage) {
  const apiMessage =
    payload && typeof payload === "object" && typeof payload.error === "string"
      ? payload.error
      : ""
  const message = unwrapErrorMessage(apiMessage) || fallbackMessage
  const error = new Error(message)
  error.status = response.status
  return error
}
