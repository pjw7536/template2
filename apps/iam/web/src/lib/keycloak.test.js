import { afterEach, expect, it, vi } from "vitest"

const adapter = vi.hoisted(() => ({
  loadUserInfo: vi.fn(),
  updateToken: vi.fn(),
  hasResourceRole: vi.fn(),
  subject: "self",
}))

vi.mock("keycloak-js", () => ({ default: class { constructor() { return adapter } } }))
afterEach(() => {
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

it("누락된 사용자 표시 정보를 UserInfo와 관리자 자기 계정에서 채웁니다", async () => {
  vi.stubGlobal("window", { __IAM_CONFIG__: { keycloakUrl: "https://sso.example.test", realm: "test" } })
  adapter.loadUserInfo.mockResolvedValue({ display_name: "홍길동" })
  adapter.hasResourceRole.mockReturnValue(true)
  const fetchProfile = vi.fn().mockResolvedValue(new Response('{"attributes":{"loginid":["gildong.hong"]}}'))
  vi.stubGlobal("fetch", fetchProfile)
  const { loadDisplayProfile } = await import("./keycloak")

  expect(await loadDisplayProfile({})).toEqual({ display_name: "홍길동", loginid: "gildong.hong" })
  expect(fetchProfile.mock.calls[0][0].pathname).toBe("/admin/realms/test/users/self")
})
