import { describe, expect, it } from "vitest"

import {
  getPortalAppDefinition,
  PORTAL_APP_CATALOG,
  shouldHideAssistantWidget,
} from "./portalAppCatalog"

describe("Portal app shell 카탈로그", () => {
  it("route gate와 navigation이 같은 앱 메타데이터를 조회한다", () => {
    expect(getPortalAppDefinition("line-dashboard")).toMatchObject({
      appName: "ESOP Dashboard",
      routeAppName: "ESOP Dashboard",
      navigationTitle: "Line Dashboard",
    })
  })

  it("개선 제외 Spider와 Teamstaff route 표시값을 그대로 보존한다", () => {
    const excluded = PORTAL_APP_CATALOG
      .filter(({ appId }) => appId.endsWith("-spider") || appId === "teamstaff")
      .map(({ appId, appName, routeAppName, prefixes }) => ({
        appId,
        appName,
        routeAppName,
        prefixes,
      }))

    expect(excluded).toEqual([
      { appId: "l3-spider", appName: "L3 Spider", routeAppName: "L3 Spider", prefixes: ["/spider/l3", "/l3_spider"] },
      { appId: "l0-spider", appName: "L0 Spider", routeAppName: "L0 Spider", prefixes: ["/l0_spider", "/fdc_trend"] },
      { appId: "l1-spider", appName: "L1 Spider", routeAppName: "L1 Spider", prefixes: [] },
      { appId: "pm-spider", appName: "PM Spider", routeAppName: "PM Spider", prefixes: ["/spider/pm", "/pm_spider"] },
      { appId: "tttm-spider", appName: "TTTM Spider", routeAppName: "TTTM Spider", prefixes: ["/spider/tttm", "/tttm_spider"] },
      { appId: "teamstaff", appName: "Teamstaff", routeAppName: "Team", prefixes: ["/teamstaff"] },
    ])
  })

  it("Assistant page와 권한 관리 화면에서만 전역 widget을 숨긴다", () => {
    expect(shouldHideAssistantWidget("/assistant/room-1")).toBe(true)
    expect(shouldHideAssistantWidget("/settings/permissions/")).toBe(true)
    expect(shouldHideAssistantWidget("/observer/EQP-1")).toBe(false)
  })
})
