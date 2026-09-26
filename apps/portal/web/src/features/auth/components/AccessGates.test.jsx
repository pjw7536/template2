import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, it, vi } from "vitest"
import { AppAccessGate } from "./AppAccessGate"
import { PortalAccessGate } from "./PortalAccessGate"

const auth = vi.hoisted(() => ({ user: {}, logout: vi.fn() }))
vi.mock("../hooks/useAuth", () => ({ useAuth: () => auth }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it("앱 권한 없으면 외부 요청 안내와 로그아웃을 제공한다", () => {
  auth.user = { scopeAccess: { emails: { allowed: false } } }
  render(<MemoryRouter><AppAccessGate scopeKey="emails" appName="메일"><p>메일 본문</p></AppAccessGate></MemoryRouter>)
  expect(screen.queryByText("메일 본문")).toBeNull()
  expect(screen.getByText(/메일이나 메신저/)).toBeTruthy()
  fireEvent.click(screen.getByRole("button", { name: "로그아웃" }))
  expect(auth.logout).toHaveBeenCalledOnce()
})

it("Portal 권한을 가진 사용자는 페이지를 본다", () => {
  auth.user = { scopeAccess: { portal: { allowed: true } } }
  render(<MemoryRouter><PortalAccessGate><p>앱 목록</p></PortalAccessGate></MemoryRouter>)
  expect(screen.getByText("앱 목록")).toBeTruthy()
})
