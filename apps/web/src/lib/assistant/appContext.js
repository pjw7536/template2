const APP_CONTEXTS = Object.freeze({
  portal: Object.freeze({
    key: "portal",
    label: "Portal",
    description: "Portal 공통 기능과 등록된 업무 앱을 안내합니다.",
  }),
  appstore: Object.freeze({
    key: "appstore",
    label: "Appstore",
    description: "업무 앱 탐색, 등록 상태와 접근 정보를 안내합니다.",
  }),
  "line-dashboard": Object.freeze({
    key: "line-dashboard",
    label: "ESOP Dashboard",
    description: "라인 상태, 이력, 알림과 수신 설정을 다룹니다.",
  }),
  observer: Object.freeze({
    key: "observer",
    label: "Observer",
    description: "장비 로그와 조회 조건 기반 분석을 지원합니다.",
  }),
  emails: Object.freeze({
    key: "emails",
    label: "Emails",
    description: "메일 검색 결과를 배경지식으로 질문할 수 있습니다.",
  }),
  "l0-spider": Object.freeze({
    key: "l0-spider",
    label: "L0 Spider",
    description: "L0 Spider의 장비와 이상 현황 업무를 다룹니다.",
  }),
  "l1-spider": Object.freeze({
    key: "l1-spider",
    label: "L1 Spider",
    description: "L1 Spider 업무 화면에 관한 질문을 지원합니다.",
  }),
  "l3-spider": Object.freeze({
    key: "l3-spider",
    label: "L3 Spider",
    description: "L3 Spider 업무 화면에 관한 질문을 지원합니다.",
  }),
  "pm-spider": Object.freeze({
    key: "pm-spider",
    label: "PM Spider",
    description: "PM Spider 업무 화면에 관한 질문을 지원합니다.",
  }),
  "tttm-spider": Object.freeze({
    key: "tttm-spider",
    label: "TTTM Spider",
    description: "TTTM Spider의 Target과 Score 업무를 다룹니다.",
  }),
  spider: Object.freeze({
    key: "spider",
    label: "Spider",
    description: "Spider 앱과 세부 분석 기능을 안내합니다.",
  }),
  "access-stats": Object.freeze({
    key: "access-stats",
    label: "접속 현황",
    description: "Portal 앱별 접속 현황과 통계를 다룹니다.",
  }),
  teamstaff: Object.freeze({
    key: "teamstaff",
    label: "Team",
    description: "기술팀 구성과 담당 정보를 안내합니다.",
  }),
  voc: Object.freeze({
    key: "voc",
    label: "VoE",
    description: "VoE 게시글과 사용자 의견 업무를 다룹니다.",
  }),
  settings: Object.freeze({
    key: "settings",
    label: "Settings",
    description: "Portal 계정, 구성원과 권한 설정을 안내합니다.",
  }),
  assistant: Object.freeze({
    key: "assistant",
    label: "Assistant",
    description: "Portal 공통 대화를 전체 화면에서 이어갑니다.",
  }),
})

const PATH_RULES = Object.freeze([
  ["/spider/l0", "l0-spider"],
  ["/l0_spider", "l0-spider"],
  ["/fdc_trend", "l0-spider"],
  ["/spider/l1", "l1-spider"],
  ["/spider/l3", "l3-spider"],
  ["/l3_spider", "l3-spider"],
  ["/spider/pm", "pm-spider"],
  ["/pm_spider", "pm-spider"],
  ["/spider/tttm", "tttm-spider"],
  ["/tttm_spider", "tttm-spider"],
  ["/esop_dashboard", "line-dashboard"],
  ["/appstore", "appstore"],
  ["/observer", "observer"],
  ["/emails", "emails"],
  ["/access-stats", "access-stats"],
  ["/teamstaff", "teamstaff"],
  ["/settings", "settings"],
  ["/assistant", "assistant"],
  ["/voc", "voc"],
  ["/spider", "spider"],
])

function normalizePathname(pathname) {
  if (typeof pathname !== "string" || !pathname.trim()) return "/"
  const normalized = pathname.trim().toLowerCase().replace(/\/+$/, "")
  return normalized || "/"
}

function matchesPath(pathname, prefix) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

export function getAssistantAppContext(appKey) {
  const normalizedKey = typeof appKey === "string" ? appKey.trim().toLowerCase() : ""
  return APP_CONTEXTS[normalizedKey] || APP_CONTEXTS.portal
}

export function resolveAssistantAppContext(pathname) {
  const normalizedPathname = normalizePathname(pathname)
  const matchedRule = PATH_RULES.find(([prefix]) => matchesPath(normalizedPathname, prefix))
  return getAssistantAppContext(matchedRule?.[1] || "portal")
}

export function buildOpenWebUIContextKey(appKey) {
  return `assistant:openwebui:${getAssistantAppContext(appKey).key}`
}
