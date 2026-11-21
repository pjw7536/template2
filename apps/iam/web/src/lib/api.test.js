import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("./keycloak.js", () => ({ admin: vi.fn() }))

import { moveMemberAffiliation, saveJobTitle, saveOriginalDepartment } from "./api.js"
import { admin } from "./keycloak.js"
import { buildOrg } from "./plan.js"

const org = buildOrg({ children: [
  { id: "t1", name: "TEAM-1", children: [{ id: "l1", name: "LINE-1", children: [{ id: "a", name: "SDWT-A" }] }] },
  { id: "t2", name: "TEAM-2", children: [{ id: "l2", name: "LINE-2", children: [{ id: "b", name: "SDWT-B" }] }] },
] })
const user = { id: "u1", username: "member", attributes: { deptname: ["TEAM-1"], user_sdwt_prod: ["SDWT-A"], line_id: ["LINE-1"], other: ["keep"] } }
const groups = [{ id: "a", path: org.sdwts.get("SDWT-A").path }, { id: "infra", path: "/headlamp-admins" }]
const writes = () => admin.mock.calls.filter(([, options]) => options?.method && options.method !== "GET")

beforeEach(() => {
  admin.mockReset()
  admin.mockImplementation(async (path) => {
    if (path === "/users/u1") return structuredClone(user)
    if (path === "/users/u1/groups") return groups
    if (path === "/group-by-path/org/TEAM-2/LINE-2/SDWT-B") return { id: "b" }
    return null
  })
})

describe("수동 프로필 속성 저장", () => {
  let current
  beforeEach(() => {
    current = structuredClone(user)
    admin.mockImplementation(async (path, options) => {
      if (path !== "/users/u1") throw new Error("사용자 외 경로를 요청했습니다.")
      if (options?.method === "PUT") current = structuredClone(options.body)
      return structuredClone(current)
    })
  })

  it("최신 속성과 직급·소속을 보존하고 직책만 저장한 결과를 읽는다", async () => {
    current.attributes.concurrent = ["new"]
    current.attributes.grdName = ["수석"]
    const saved = await saveJobTitle("u1", " PL ", "")
    expect(saved.attributes).toEqual({ ...user.attributes, concurrent: ["new"], grdName: ["수석"], job_title: ["PL"] })
    expect(writes()).toHaveLength(1)
    expect(admin.mock.calls.at(-1)[0]).toBe("/users/u1")
  })

  it("빈 직책은 속성을 지우며 다른 속성은 보존한다", async () => {
    current.attributes.job_title = ["파트장"]
    await saveJobTitle("u1", " ", "파트장")
    expect(current.attributes).toEqual(user.attributes)
  })

  it("화면을 연 뒤 직책이 바뀌었으면 저장하지 않는다", async () => {
    current.attributes.job_title = ["파트장"]
    await expect(saveJobTitle("u1", "PL", "")).rejects.toThrow("다른 관리자가 직책을 변경")
    expect(writes()).toEqual([])
  })

  it("프로필에서 직책이 저장되지 않으면 성공으로 처리하지 않는다", async () => {
    admin.mockImplementation(async () => structuredClone(user))
    await expect(saveJobTitle("u1", "PL", "")).rejects.toThrow("User Profile")
  })

  it("너무 긴 직책은 요청 전에 막는다", async () => {
    await expect(saveJobTitle("u1", "a".repeat(81), "")).rejects.toThrow("80자")
    expect(admin).not.toHaveBeenCalled()
  })

  it("저장 실패를 전달하고 성공 결과를 반환하지 않는다", async () => {
    admin.mockImplementation(async (path, options) => {
      if (options?.method === "PUT") throw new Error("HTTP 403")
      return structuredClone(user)
    })
    await expect(saveJobTitle("u1", "PL", "")).rejects.toThrow("HTTP 403")
  })

  it("SSO 부서와 현재 소속을 유지하며 원소속 부서를 저장하고 비울 수 있다", async () => {
    current.attributes.deptname = ["파견팀"]
    const attributes = { ...current.attributes }
    const saved = await saveOriginalDepartment("u1", " 기존팀 ", "")
    expect(saved.attributes).toEqual({ ...attributes, original_deptname: ["기존팀"] })
    const cleared = await saveOriginalDepartment("u1", "", "기존팀")
    expect(cleared.attributes).toEqual(attributes)
    expect(writes().map(([path]) => path)).toEqual(["/users/u1", "/users/u1"])
  })

  it("다른 관리자가 원소속 부서를 먼저 바꿨으면 저장하지 않는다", async () => {
    current.attributes.original_deptname = ["수정된팀"]
    await expect(saveOriginalDepartment("u1", "기존팀", "")).rejects.toThrow("다른 관리자가 원소속 부서를 변경")
    expect(writes()).toEqual([])
  })
})

describe("구성원 SDWT 이동", () => {
  it("최신 소속을 확인하고 그룹·소속 속성만 변경하며 다른 권한과 저장 직전 속성을 유지한다", async () => {
    let reads = 0
    const implementation = admin.getMockImplementation()
    admin.mockImplementation(async (path, options) => {
      if (path === "/users/u1" && !options?.method && ++reads === 2) {
        return { ...user, attributes: { ...user.attributes, concurrent: ["new"] } }
      }
      return implementation(path, options)
    })
    await moveMemberAffiliation("u1", "SDWT-A", "SDWT-B", org)
    expect(writes()).toEqual([
      ["/users/u1/groups/a", { method: "DELETE" }],
      ["/users/u1/groups/b", { method: "PUT" }],
      ["/users/u1", { method: "PUT", body: { ...user, attributes: {
        ...user.attributes, user_sdwt_prod: ["SDWT-B"], line_id: ["LINE-2"], concurrent: ["new"],
      } } }],
    ])
  })

  it.each([["SDWT-A", "SDWT-A"], ["SDWT-A", "missing"], ["missing", "SDWT-B"]])("잘못된 대상(%s → %s)은 API 호출 전에 차단한다", async (from, to) => {
    await expect(moveMemberAffiliation("u1", from, to, org)).rejects.toThrow()
    expect(admin).not.toHaveBeenCalled()
  })

  it("화면 표시 이후 소속이 바뀌었으면 덮어쓰지 않는다", async () => {
    const implementation = admin.getMockImplementation()
    admin.mockImplementation((path, options) => path === "/users/u1/groups" ? [] : implementation(path, options))
    await expect(moveMemberAffiliation("u1", "SDWT-A", "SDWT-B", org)).rejects.toThrow("소속이 변경되었습니다")
    expect(writes()).toEqual([])
  })

  it("그룹 변경이 실패하면 다음 변경을 시도하지 않고 오류를 전달한다", async () => {
    const implementation = admin.getMockImplementation()
    admin.mockImplementation((path, options) => {
      if (options?.method === "DELETE") throw new Error("HTTP 403")
      return implementation(path, options)
    })
    await expect(moveMemberAffiliation("u1", "SDWT-A", "SDWT-B", org)).rejects.toThrow("HTTP 403")
    expect(writes()).toHaveLength(1)
  })

  it("이전 소속 해제 후 새 그룹 가입이 실패하면 속성을 저장하거나 역할을 변경하지 않는다", async () => {
    const implementation = admin.getMockImplementation()
    admin.mockImplementation((path, options) => {
      if (path === "/users/u1/groups/b" && options?.method === "PUT") throw new Error("가입 실패")
      return implementation(path, options)
    })
    await expect(moveMemberAffiliation("u1", "SDWT-A", "SDWT-B", org)).rejects.toThrow("가입 실패")
    expect(writes()).toEqual([
      ["/users/u1/groups/a", { method: "DELETE" }],
      ["/users/u1/groups/b", { method: "PUT" }],
    ])
  })
})
