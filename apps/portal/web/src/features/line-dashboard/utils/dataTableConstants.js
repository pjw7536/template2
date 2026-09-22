// src/features/line-dashboard/utils/dataTableConstants.js
// 데이터 테이블 전역에서 재사용하는 상수와 포맷터들입니다.
export const DEFAULT_TABLE = "drone_sop"
export const DEFAULT_RANGE_DAYS = 3

const DAY_IN_MS = 86_400_000

// Date 객체를 YYYY-MM-DD 문자열로 바꿔 폼 입력과 호환되게 만듭니다.
export const toDateInputValue = (date) => date.toISOString().split("T")[0]

export const getDefaultFromValue = () => {
  const now = new Date()
  const from = new Date(now.getTime() - DEFAULT_RANGE_DAYS * DAY_IN_MS)
  return toDateInputValue(from)
}

export const getDefaultToValue = () => toDateInputValue(new Date())

// 셀 저장 인디케이터 노출 시간을 제어하는 값들입니다.
export const SAVING_DELAY_MS = 180
export const MIN_SAVING_VISIBLE_MS = 500
export const SAVED_VISIBLE_MS = 800

// 프로세스 플로우와 관련된 컬럼 키 목록입니다.
export const STEP_COLUMN_KEYS = [
  "main_step",
  "metro_steps",
  "metro_current_step",
  "metro_end_step",
  "custom_end_step",
  "inform_step",
]

export const STEP_COLUMN_KEY_SET = new Set(STEP_COLUMN_KEYS)

export { numberFormatter, timeFormatter } from "./formatters"
