import { describe, expect, it } from "vitest"
import { buildColumns, cellState, planChange, readCatalog } from "./access.js"

const CATALOG = {
  apps: [
    { client: "portal", uuid: "p-1", name: "Portal", features: [
      { key: "emails", name: "Emails", default: "open" },
      { key: "access-stats", name: "접속 현황", default: "closed" },
    ] },
    { client: "airflow", uuid: "a-1", name: "Airflow", default: "open" },
    { group: "/headlamp-admins", name: "Headlamp", infra: true },
  ],
}
const [portalAll, emails, stats, airflow, headlamp] = buildColumns(CATALOG)

function access({ direct = [], effective = direct, groups = [] } = {}) {
  return {
    clients: { portal: { direct: new Set(direct), effective: new Set(effective) } },
    groups: new Set(groups),
  }
}

describe("카탈로그", () => {
  it("순서가 섞인 조각을 순번대로 이어 읽는다", () => {
    const text = JSON.stringify(CATALOG)
    const parts = [text.slice(0, 100), text.slice(100)].map((part, index) => `00${index}:${part}`)
    expect(readCatalog([...parts].reverse())).toEqual(CATALOG)
    expect(() => readCatalog([])).toThrow()
  })

  it("Portal은 전체 묶음 열과 기능 열, 단일 앱은 한 열이 된다", () => {
    expect(portalAll).toMatchObject({ label: "Portal 전체", roles: { admin: "all:admin" }, bundle: true })
    expect(emails).toMatchObject({ roles: { user: "emails:user" }, closed: false })
    expect(stats).toMatchObject({ closed: true })
    expect(airflow).toMatchObject({ roles: { viewer: "viewer" }, uuid: "a-1" })
    expect(headlamp).toMatchObject({ group: "/headlamp-admins", infra: true })
  })
})

describe("셀 상태", () => {
  it("직접 부여와 기본·묶음·SDWT 앱 역할로 받은 권한을 구분한다", () => {
    expect(cellState(emails, access({ direct: ["emails:admin"], effective: ["emails:admin", "emails:user", "emails:viewer"] })))
      .toMatchObject({ level: "admin", source: "direct" })
    expect(cellState(emails, access({ effective: ["emails:viewer"] }))).toMatchObject({ level: "viewer", source: "inherited" })
    expect(cellState(emails, access({ direct: ["emails:viewer"], effective: ["emails:viewer", "emails:user"] })))
      .toMatchObject({ level: "user", direct: "viewer", source: "inherited" })
    expect(cellState(stats, access())).toMatchObject({ level: null, source: "none" })
    expect(cellState(airflow, access()).source).toBe("unavailable")
  })

  it("그룹 열은 가입 여부로 판정한다", () => {
    expect(cellState(headlamp, access({ groups: ["/headlamp-admins"] }))).toMatchObject({ level: "admin", source: "direct" })
  })
})

describe("변경 계획", () => {
  it("이 열의 직접 역할만 바꾸고 다른 열 역할은 건드리지 않는다", () => {
    const current = access({ direct: ["emails:user", "access-stats:admin"] })
    expect(planChange(emails, current, { level: "admin" })).toEqual({ add: ["emails:admin"], remove: ["emails:user"] })
    expect(planChange(emails, current, { level: null })).toEqual({ add: [], remove: ["emails:user"] })
    expect(planChange(stats, current, { level: "admin" })).toEqual({ add: [], remove: [] })
    expect(planChange(headlamp, access(), { level: "admin" })).toEqual({ add: ["/headlamp-admins"], remove: [] })
  })
})
