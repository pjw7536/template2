// src/features/line-dashboard/utils/toast.js
// Shadcn Studio sonner 팝업의 outline 스타일을 재사용합니다.
export const TOAST_BASE_STYLE = {
  "--normal-bg": "var(--background)",
  "--normal-text": "var(--foreground)",
  "--normal-border": "var(--border)",
  "--border-radius": "calc(var(--radius) + 2px)",
}

const TOAST_ACCENTS = {
  success: "light-dark(var(--color-green-600), var(--color-green-400))",
  warning: "light-dark(var(--color-amber-600), var(--color-amber-400))",
  destructive: "var(--destructive)",
  info: "light-dark(var(--color-sky-600), var(--color-sky-400))",
  primary: "var(--primary)",
}

/**
 * 공통 스타일에 색상/지속시간만 입혀서 반환합니다.
 * - intent: success | warning | destructive | info | primary
 * - color: 아웃라인/텍스트에 적용할 강조색 (직접 지정 시 intent보다 우선)
 * - duration: 토스트 유지 시간(ms)
 */
export function buildToastOptions({ intent = "info", color, duration = 2000 } = {}) {
  const accentColor = color ?? TOAST_ACCENTS[intent] ?? TOAST_ACCENTS.info

  return {
    duration,
    style: {
      ...TOAST_BASE_STYLE,
      "--normal-text": accentColor,
      "--normal-border": accentColor,
    },
  }
}
