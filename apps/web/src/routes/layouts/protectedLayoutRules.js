const LINE_DASHBOARD_PREFIX = "/esop_dashboard"
const EMAILS_PREFIX = "/emails"
const MODELS_PREFIX = "/models"
const SETTINGS_PREFIX = "/settings"
const VOC_ROUTE_PATTERN = /\/voc(\/|$)|\/qna(\/|$)/
const INTERNAL_SCROLL_PREFIXES = ["/emails", "/appstore"]

export const LAYOUT_VARIANTS = {
  DEFAULT: "default",
  LINE_DASHBOARD: "line-dashboard",
  EMAILS: "emails",
  MODELS: "models",
  SETTINGS: "settings",
  VOC: "voc",
}

// 순서 중요: 먼저 매칭되는 규칙을 사용한다.
const ROUTE_LAYOUT_RULES = [
  {
    name: "line-dashboard",
    variant: LAYOUT_VARIANTS.LINE_DASHBOARD,
    matches: (pathname) => pathname.startsWith(LINE_DASHBOARD_PREFIX),
  },
  {
    name: "emails",
    variant: LAYOUT_VARIANTS.EMAILS,
    matches: (pathname) => pathname.startsWith(EMAILS_PREFIX),
  },
  {
    name: "models",
    variant: LAYOUT_VARIANTS.MODELS,
    matches: (pathname) => pathname.startsWith(MODELS_PREFIX),
  },
  {
    name: "settings",
    variant: LAYOUT_VARIANTS.SETTINGS,
    matches: (pathname) => pathname.startsWith(SETTINGS_PREFIX),
  },
  {
    name: "voc",
    variant: LAYOUT_VARIANTS.VOC,
    matches: (pathname) => VOC_ROUTE_PATTERN.test(pathname),
  },
]

function normalizePathname(pathname) {
  return typeof pathname === "string" ? pathname.toLowerCase() : ""
}

function getLayoutVariant(pathname) {
  const normalizedPath = normalizePathname(pathname)
  const matchedRule = ROUTE_LAYOUT_RULES.find((rule) => rule.matches(normalizedPath))
  return matchedRule?.variant ?? LAYOUT_VARIANTS.DEFAULT
}

export function getProtectedLayoutConfig(pathname) {
  const normalizedPath = normalizePathname(pathname)
  const isVocRoute = VOC_ROUTE_PATTERN.test(normalizedPath)
  const isInternalScrollRoute = INTERNAL_SCROLL_PREFIXES.some((prefix) =>
    normalizedPath.startsWith(prefix),
  )

  return {
    variant: getLayoutVariant(normalizedPath),
    scrollAreaClassName: isVocRoute || isInternalScrollRoute ? "overflow-hidden" : undefined,
  }
}
