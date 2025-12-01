// src/features/line-dashboard/utils/formatters.js
// 라인 대시보드 전반에서 공유하는 숫자/시간 포맷터

const LOCALE = "ko-KR"
const TIME_ZONE = "Asia/Seoul"

export const numberFormatter = new Intl.NumberFormat(LOCALE)
export const timeFormatter = new Intl.DateTimeFormat(LOCALE, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: TIME_ZONE,
})
