export const DEFAULT_CHAT_WIDTH = 820
export const DEFAULT_CHAT_HEIGHT = 720
const MIN_CHAT_WIDTH = 360
const MIN_CHAT_HEIGHT = 420
const MAX_CHAT_WIDTH = 1000
const MAX_CHAT_HEIGHT = 1500
const VIEWPORT_PADDING = 24
const MAX_VISIBLE_HEIGHT_RATIO = 0.8

export const DEFAULT_FLOATING_BUTTON_SIZE = 48

export function clampPosition(x, y, width, height) {
  if (typeof window === "undefined") return { x, y }
  return {
    x: Math.min(Math.max(x, 8), window.innerWidth - width - 8),
    y: Math.min(Math.max(y, 8), window.innerHeight - height - 8),
  }
}

export function clampSize(width, height) {
  if (typeof window === "undefined") {
    return { width, height }
  }

  const maxAllowedWidth = Math.max(window.innerWidth - VIEWPORT_PADDING, 240)
  const maxViewportHeight = Math.max(window.innerHeight - VIEWPORT_PADDING, 320)
  const maxVisibleHeight = window.innerHeight * MAX_VISIBLE_HEIGHT_RATIO
  const maxAllowedHeight = Math.min(maxViewportHeight, maxVisibleHeight)
  const minAllowedWidth = Math.min(MIN_CHAT_WIDTH, maxAllowedWidth)
  const minAllowedHeight = Math.min(MIN_CHAT_HEIGHT, maxAllowedHeight)
  const maxWidth = Math.max(minAllowedWidth, Math.min(MAX_CHAT_WIDTH, maxAllowedWidth))
  const maxHeight = Math.max(minAllowedHeight, Math.min(MAX_CHAT_HEIGHT, maxAllowedHeight))

  return {
    width: Math.min(Math.max(width, minAllowedWidth), maxWidth),
    height: Math.min(Math.max(height, minAllowedHeight), maxHeight),
  }
}
