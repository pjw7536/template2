import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { MembersAccessDialogs } from "./MembersAccessDialogs"

function createClosedDialogConfigs() {
  return {
    grantDialog: {
      open: false,
      userSdwtProd: "ETCH_A",
      search: "",
      userId: "",
      role: "viewer",
      reason: "",
      candidates: [],
      isCandidatesPending: false,
      isPending: false,
      onOpenChange: vi.fn(),
      onSearchChange: vi.fn(),
      onUserIdChange: vi.fn(),
      onRoleChange: vi.fn(),
      onReasonChange: vi.fn(),
      onConfirm: vi.fn(),
    },
    roleChangeDialog: {
      target: null,
      reason: "",
      isPending: false,
      onReasonChange: vi.fn(),
      onClose: vi.fn(),
      onConfirm: vi.fn(),
    },
    revokeDialog: {
      target: null,
      userSdwtProd: "ETCH_A",
      reason: "",
      isPending: false,
      onReasonChange: vi.fn(),
      onClose: vi.fn(),
      onConfirm: vi.fn(),
    },
  }
}

describe("Account 멤버 권한 dialog", () => {
  it("거절 대상을 표시하고 취소 동작을 부모 handler에 위임한다", () => {
    const onClose = vi.fn()
    render(
      <MembersAccessDialogs
        {...createClosedDialogConfigs()}
        rejectDialog={{
          target: { name: "홍길동" },
          reason: "",
          isPending: false,
          onReasonChange: vi.fn(),
          onClose,
          onConfirm: vi.fn(),
        }}
      />,
    )

    expect(screen.getByText("홍길동님의 소속 변경 요청을 거절합니다.")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "취소" }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
