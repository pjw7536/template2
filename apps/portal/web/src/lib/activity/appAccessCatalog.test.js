import { describe, expect, it } from "vitest"

import {
  APP_ACCESS_RULES,
  getAppAccessDefinition,
  resolveAppAccessTarget,
} from "./appAccessCatalog"

describe("앱 접속 추적 카탈로그", () => {
  it("appId 기준 조회와 경로 조회가 같은 정의를 반환한다", () => {
    expect(resolveAppAccessTarget("/access-stats")).toBe(
      getAppAccessDefinition("access-stats"),
    )
  })

  it("개선 제외 Spider와 Teamstaff 항목을 그대로 보존한다", () => {
    const excludedEntries = APP_ACCESS_RULES
      .filter(({ appId }) => appId.endsWith("-spider") || appId === "teamstaff")
      .map(({ appId, appName, prefixes }) => ({ appId, appName, prefixes }))

    expect(excludedEntries).toEqual([
      { appId: "l3-spider", appName: "L3 Spider", prefixes: ["/spider/l3", "/l3_spider"] },
      { appId: "l0-spider", appName: "L0 Spider", prefixes: ["/l0_spider", "/fdc_trend"] },
      { appId: "l1-spider", appName: "L1 Spider", prefixes: [] },
      { appId: "pm-spider", appName: "PM Spider", prefixes: ["/spider/pm", "/pm_spider"] },
      { appId: "tttm-spider", appName: "TTTM Spider", prefixes: ["/spider/tttm", "/tttm_spider"] },
      { appId: "teamstaff", appName: "Teamstaff", prefixes: ["/teamstaff"] },
    ])
  })
})
