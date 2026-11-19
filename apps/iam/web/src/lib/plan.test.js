import { describe, expect, it } from "vitest"
import { readSdwtCsv, readUserCsv } from "./csv.js"
import { buildOrg, orgRoleName, parseOrgRole, planAffiliation, planOrg, sdwtLevels, sdwtRolePlan, withAffiliation } from "./plan.js"

const ORG = {
  id: "org", name: "org",
  children: [{
    id: "t1", name: "TEAM-1",
    children: [{
      id: "l1", name: "LINE-1",
      children: [{ id: "a", name: "SDWT-A" }, { id: "b", name: "SDWT-B" }],
    }],
  }],
}
const H = "user_sdwt_prod,line_id,department"

describe("CSV", () => {
  it("목록 CSV의 BOM·따옴표를 읽고 규칙 위반을 모은다", () => {
    expect(readSdwtCsv(`\uFEFF${H}\r\n"SDWT-A",LINE-1,TEAM-1\n`).items).toEqual([{ sdwt: "SDWT-A", line: "LINE-1", team: "TEAM-1" }])
    for (const text of [`${H}\n`, `${H}\nA,L,T\nA,L2,T\n`, `${H}\nA/x,L,T\n`, `${H}\nA:x,L,T\n`, `${H}\nA,L,\n`]) {
      expect(readSdwtCsv(text).errors.length, text).toBeGreaterThan(0)
    }
  })

  it("사용자 CSV는 추가 열을 허용하고 빈 SDWT를 소속 없음으로 읽는다", () => {
    const result = readUserCsv("userid,user_sdwt_prod,sabun\n001,SDWT-A,S1\n002,,S2\n")
    expect(result.items.map(({ userid, sdwt }) => [userid, sdwt])).toEqual([["001", "SDWT-A"], ["002", ""]])
  })
})

describe("소속 트리", () => {
  it("/org 아래를 팀→라인→SDWT로 읽는다", () => {
    const org = buildOrg(ORG)
    expect(org.teams.map((team) => team.path)).toEqual(["/org/TEAM-1"])
    expect(org.sdwts.get("SDWT-A")).toMatchObject({ team: "TEAM-1", line: "LINE-1", path: "/org/TEAM-1/LINE-1/SDWT-A" })
  })

  it("없는 팀·라인·SDWT 그룹만 만들고 새 SDWT 목록을 돌려준다", () => {
    const plan = planOrg(ORG, [{ sdwt: "SDWT-A", line: "LINE-1", team: "TEAM-1" }, { sdwt: "SDWT-C", line: "LINE-1", team: "TEAM-2" }])
    expect(plan.errors).toEqual([])
    expect(plan.creates).toEqual(["/org/TEAM-2", "/org/TEAM-2/LINE-1", "/org/TEAM-2/LINE-1/SDWT-C"])
    expect(plan.sdwts.map((item) => item.sdwt)).toEqual(["SDWT-C"])
  })

  it("SDWT가 다른 위치에 있으면 만들지 않는다", () => {
    expect(planOrg(ORG, [{ sdwt: "SDWT-A", line: "LINE-2", team: "TEAM-1" }]).errors.length).toBe(1)
  })
})

describe("소속별 역할", () => {
  it("이름을 만들고 읽는다", () => {
    expect(orgRoleName({ sdwt: "SDWT-A" }, "admin")).toBe("sdwt:SDWT-A:admin")
    expect(orgRoleName({ team: "T", line: "L" }, "user")).toBe("team:T:line:L:user")
    expect(orgRoleName({ team: "T" }, "viewer")).toBe("team:T:viewer")
    expect(parseOrgRole("team:T:line:L:user")).toMatchObject({ kind: "line", team: "T", line: "L", level: "user" })
    expect(parseOrgRole("team:T:admin")).toMatchObject({ kind: "team", team: "T", level: "admin" })
    expect(parseOrgRole("sdwt:SDWT-A:viewer")).toMatchObject({ kind: "sdwt", sdwt: "SDWT-A", level: "viewer" })
    expect(parseOrgRole("org-all")).toBeNull()
    expect(parseOrgRole("SDWT-A:viewer")).toBeNull()
  })

  it("펼쳐진 역할에서 SDWT별 가장 높은 등급을 구한다", () => {
    expect(sdwtLevels(["sdwt:SDWT-A:user", "sdwt:SDWT-A:admin", "sdwt:SDWT-B:viewer", "team:T:admin", "team:T:line:L:admin", "org-all"])).toEqual({ "SDWT-A": "admin", "SDWT-B": "viewer" })
  })

  it("새 SDWT 역할은 라인·팀 역할에 들어간다", () => {
    expect(sdwtRolePlan({ team: "T", line: "L", sdwt: "S" })[2]).toEqual({ role: "sdwt:S:admin", parents: ["team:T:line:L:admin", "team:T:admin"] })
  })
})

describe("소속 변경", () => {
  const org = buildOrg(ORG)
  const attributes = { user_sdwt_prod: ["SDWT-A"], line_id: ["LINE-1"], deptname: ["TEAM-1"], sabun: ["S1"] }

  it("이전 소속 그룹에서 빠지고 새 SDWT 그룹에 들어간다. 다른 그룹은 그대로다", () => {
    const plan = planAffiliation({ attributes, org, newSdwt: "SDWT-B", groupPaths: ["/org/TEAM-1/LINE-1/SDWT-A", "/iam/platform-admins"] })
    expect(plan.remove).toEqual(["/org/TEAM-1/LINE-1/SDWT-A"])
    expect(plan.add).toEqual(["/org/TEAM-1/LINE-1/SDWT-B"])
    expect(withAffiliation(attributes, plan)).toEqual({ user_sdwt_prod: ["SDWT-B"], line_id: ["LINE-1"], deptname: ["TEAM-1"], sabun: ["S1"] })
  })

  it("같은 소속이면 바뀌지 않고, 부서와 다른 팀이면 경고하며, 소속 없음은 모두 뺀다", () => {
    expect(planAffiliation({ attributes, org, newSdwt: "SDWT-A", groupPaths: ["/org/TEAM-1/LINE-1/SDWT-A"] }).changed).toBe(false)
    expect(planAffiliation({ attributes: { ...attributes, deptname: ["X"] }, org, newSdwt: "SDWT-A", groupPaths: [] }).teamMismatch).toBe(true)
    const none = planAffiliation({ attributes, org, newSdwt: "", groupPaths: ["/org/TEAM-1/LINE-1/SDWT-A"] })
    expect(none.remove).toEqual(["/org/TEAM-1/LINE-1/SDWT-A"])
    expect(withAffiliation(attributes, none)).toEqual({ deptname: ["TEAM-1"], sabun: ["S1"] })
    expect(planAffiliation({ attributes, org, newSdwt: "NOPE", groupPaths: [] }).error).toBeTruthy()
  })
})
