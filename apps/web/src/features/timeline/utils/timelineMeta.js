/**
 * 각 로그 타입(logType)별 컬러 매핑.
 * 클래스 이름은 timeline.css에서 디자인 토큰 기반 색상으로 연결됩니다.
 */
export const groupConfig = {
  EQP: {
    stateClasses: {
      RUN: "timeline-color-eqp-run",
      DOWN: "timeline-color-eqp-down",
      PM: "timeline-color-eqp-pm",
      IDLE: "timeline-color-eqp-idle",
      LOCAL: "timeline-color-eqp-local",
    },
  },
  TIP: {
    stateClasses: {
      OPEN: "timeline-color-tip-open",
      CLOSE: "timeline-color-tip-close",
    },
  },
  RACB: {
    stateClasses: {
      ALARM: "timeline-color-racb-alarm",
      WARN: "timeline-color-racb-warn",
    },
  },
  CTTTM: {
    stateClasses: {
      CBM: "timeline-color-ctttm-cbm",
      NSP: "timeline-color-ctttm-nsp",
    },
  },
  JIRA: {
    stateClasses: {
      ISSUED: "timeline-color-jira-issued",
      CLOSED: "timeline-color-jira-closed",
    },
  },
};
