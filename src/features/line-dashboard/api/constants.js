// src/features/line-dashboard/api/constants.js
// API 유틸 전반에서 공유하는 정규식/상수 모음입니다.
export const SAFE_IDENTIFIER = /^[A-Za-z0-9_]+$/

// YYYY-MM-DD 포맷 검사에 사용됩니다.
export const DATE_ONLY_REGEX = /^\d{4}-\d{2}-\d{2}$/

// 타임스탬프 후보 컬럼 이름 목록(우선순위 순).
export const DATE_COLUMN_CANDIDATES = ["created_at", "updated_at", "timestamp", "ts", "date"]

// 라인 요약 데이터를 저장하는 기본 테이블 이름입니다.
export const LINE_SDWT_TABLE_NAME = "line_sdwt"
