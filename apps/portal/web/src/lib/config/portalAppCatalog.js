const definitions = [
  {
    appId: "home",
    appName: "Portal Home",
    routeAppName: "Portal Home",
    requiresAppAccess: false,
    matches: (pathname) => pathname === "/",
  },
  {
    appId: "appstore",
    appName: "Appstore",
    routeAppName: "Appstore",
    prefixes: ["/appstore"],
  },
  {
    appId: "line-dashboard",
    appName: "ESOP Dashboard",
    routeAppName: "ESOP Dashboard",
    navigationTitle: "Line Dashboard",
    prefixes: ["/ESOP_Dashboard/tip-status"],
    requiredAppScopes: ["line-dashboard", "observer"],
  },
  {
    appId: "line-dashboard",
    appName: "ESOP Dashboard",
    routeAppName: "ESOP Dashboard",
    navigationTitle: "Line Dashboard",
    prefixes: ["/ESOP_Dashboard", "/esop_dashboard"],
  },
  {
    appId: "l3-spider",
    appName: "L3 Spider",
    routeAppName: "L3 Spider",
    prefixes: ["/spider/l3", "/l3_spider"],
  },
  {
    appId: "l0-spider",
    appName: "L0 Spider",
    routeAppName: "L0 Spider",
    navigationTitle: "Spider",
    matches: (pathname) => pathname === "/spider/l0",
    prefixes: ["/l0_spider", "/fdc_trend"],
  },
  {
    appId: "l1-spider",
    appName: "L1 Spider",
    routeAppName: "L1 Spider",
    matches: (pathname) => pathname === "/spider/l1",
    prefixes: [],
  },
  {
    appId: "pm-spider",
    appName: "PM Spider",
    routeAppName: "PM Spider",
    prefixes: ["/spider/pm", "/pm_spider"],
  },
  {
    appId: "tttm-spider",
    appName: "TTTM Spider",
    routeAppName: "TTTM Spider",
    prefixes: ["/spider/tttm", "/tttm_spider"],
  },
  {
    appId: "teamstaff",
    appName: "Teamstaff",
    routeAppName: "Team",
    prefixes: ["/teamstaff"],
  },
  {
    appId: "observer",
    appName: "Observer",
    routeAppName: "Observer",
    prefixes: ["/observer"],
  },
  {
    appId: "emails",
    appName: "Emails",
    routeAppName: "메일함",
    navigationTitle: "Emails",
    prefixes: ["/emails"],
  },
  {
    appId: "voc",
    appName: "VoE",
    routeAppName: "VoE",
    prefixes: ["/voc"],
  },
  {
    appId: "settings",
    appName: "Settings",
    routeAppName: "Settings",
    navigationTitle: "Settings",
    requiresAppAccess: false,
    prefixes: ["/settings"],
  },
  {
    appId: "assistant",
    appName: "Assistant",
    routeAppName: "Assistant",
    prefixes: ["/assistant"],
  },
  {
    appId: "access-stats",
    appName: "접속 현황",
    routeAppName: "접속 현황",
    prefixes: ["/access-stats"],
  },
]

export const PORTAL_APP_CATALOG = Object.freeze(definitions.map((definition) => Object.freeze({
  ...definition,
  prefixes: definition.prefixes
    ? Object.freeze([...definition.prefixes])
    : definition.prefixes,
  requiredAppScopes: definition.requiredAppScopes
    ? Object.freeze([...definition.requiredAppScopes])
    : definition.requiredAppScopes,
})))

export function getPortalAppDefinition(appId) {
  if (typeof appId !== "string") return null
  const normalizedId = appId.trim().toLowerCase()
  return PORTAL_APP_CATALOG.find(({ appId: candidateId }) => candidateId === normalizedId) ?? null
}

export const ASSISTANT_WIDGET_HIDDEN_PATHS = Object.freeze([
  "/settings/members",
  "/settings/permissions",
])

export function shouldHideAssistantWidget(pathname) {
  const normalizedPath = typeof pathname === "string"
    ? pathname.replace(/\/+$/, "").toLowerCase()
    : ""
  return normalizedPath === "/assistant"
    || normalizedPath.startsWith("/assistant/")
    || ASSISTANT_WIDGET_HIDDEN_PATHS.includes(normalizedPath)
}
