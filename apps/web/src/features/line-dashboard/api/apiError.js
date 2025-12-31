// 파일 경로: src/features/line-dashboard/api/apiError.js
import { unwrapErrorMessage } from "../utils/lineSettings"

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
