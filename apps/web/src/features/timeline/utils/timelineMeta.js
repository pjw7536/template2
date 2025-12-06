/**
 * 각 로그 타입(logType)별 컬러 매핑
 * Tailwind 색상 클래스로 작성 (timeline.css @apply 로 색 지정)
 */
export const groupConfig = {
  EQP: {
    stateColors: {
      RUN: "bg-blue-600 border-blue-700",
      IDLE: "bg-green-600 border-green-700",
      PM: "bg-yellow-600 border-yellow-700",
      DOWN: "bg-red-600 border-red-700",
    },
  },
  TIP: {
    stateColors: {
      OPEN: "bg-blue-600 border-blue-700",
      CLOSE: "bg-red-600 border-red-700",
    },
  },
  RACB: {
    stateColors: {
      ALARM: "bg-red-600 border-red-700",
      WARN: "bg-amber-600 border-amber-700",
    },
  },
  CTTTM: {
    stateColors: {
      TTM_FAIL: "bg-red-600 border-red-700",
      TTM_WARN: "bg-yellow-600 border-yellow-700",
    },
  },
  JIRA: {
    stateColors: {
      ISSUED: "bg-blue-600 border-blue-700",
      CLOSED: "bg-purple-600 border-purple-700",
    },
  },
};
