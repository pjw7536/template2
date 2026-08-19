import { isRouteErrorResponse } from "react-router-dom"

function normalizeSafeText(value, maxLength) {
  if (typeof value !== "string") return ""
  const printable = Array.from(value, (character) => {
    const codePoint = character.codePointAt(0)
    return codePoint <= 31 || codePoint === 127 ? " " : character
  }).join("")
  return printable.trim().slice(0, maxLength)
}

export function normalizeRouteError(error) {
  if (!isRouteErrorResponse(error)) {
    return {
      title: "Something went wrong",
      description: "An unexpected error occurred. Please try again or head back home.",
      statusLabel: "",
    }
  }

  const data = error.data && typeof error.data === "object" ? error.data : null
  const code = normalizeSafeText(data?.code, 80)
  const message = normalizeSafeText(data?.message, 240)
  const status = Number.isInteger(error.status) ? error.status : null
  const isNotFound = status === 404

  return {
    title: isNotFound ? "Page not found" : "Request could not be completed",
    description:
      message ||
      (isNotFound
        ? "The page you are looking for does not exist or has been moved."
        : "The requested page is temporarily unavailable. Please try again or head back home."),
    statusLabel: [status ? `HTTP ${status}` : "", code].filter(Boolean).join(" · "),
  }
}
