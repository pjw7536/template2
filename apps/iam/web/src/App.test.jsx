import { renderToStaticMarkup } from "react-dom/server"
import { afterEach, expect, it, vi } from "vitest"

import { keycloak } from "@/lib/keycloak"
import App from "./App"

vi.mock("@/lib/keycloak", () => ({
  keycloak: { idTokenParsed: {}, tokenParsed: { preferred_username: "90000101" } },
  realm: "fixture",
  admin: vi.fn(),
  canManageUsers: () => false,
  loadDisplayProfile: vi.fn(),
}))

afterEach(() => vi.unstubAllGlobals())

it("접근 권한이 없어도 사람 이름과 로그인 ID를 표시하고 EPID를 대신 표시하지 않습니다", () => {
  vi.stubGlobal("location", { hash: "" })
  keycloak.idTokenParsed = { display_name: "홍길동", loginid: "gildong.hong" }

  const html = renderToStaticMarkup(<App />)

  expect(html).toContain("Etch Members")
  expect(html).toContain("홍길동(gildong.hong)")
  expect(html).not.toContain("90000101")
  expect(html).toContain("플랫폼 관리자 등록을 요청")
})

it("ID Token과 액세스 토큰에서 표시값을 함께 읽습니다", () => {
  vi.stubGlobal("location", { hash: "" })
  keycloak.idTokenParsed = { display_name: "홍길동" }
  keycloak.tokenParsed = { loginid: ["gildong.hong"], preferred_username: "90000101" }
  expect(renderToStaticMarkup(<App />)).toContain("홍길동(gildong.hong)")
})
