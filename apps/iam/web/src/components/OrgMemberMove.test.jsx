import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

vi.mock("@dnd-kit/dom", () => ({ PointerActivationConstraints: {} }))
vi.mock("@dnd-kit/react", () => ({
  DragDropProvider: ({ children }) => children,
  DragOverlay: () => null,
  PointerSensor: { configure: () => ({}) },
  useDraggable: vi.fn(() => ({ ref: undefined, handleRef: undefined, isDragSource: false })),
  useDroppable: vi.fn(() => ({ ref: undefined, isDropTarget: false })),
}))
vi.mock("react-dom", async (original) => ({ ...await original(), createPortal: (children) => children }))
vi.mock("../lib/api.js", () => ({ moveMemberAffiliation: vi.fn() }))

import { useDraggable, useDroppable } from "@dnd-kit/react"
import { MemberMoveProvider, MovableMember, SdwtDropTarget } from "./OrgMemberMove.jsx"

const user = { id: "u1", username: "member", attributes: { display_name: ["테스트 구성원"] } }
const sdwt = { id: "s1", name: "SDWT-A" }

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("document", { body: {}, fullscreenElement: null })
})

function render(editing, disabled = false) {
  return renderToStaticMarkup(
    <MemberMoveProvider org={{}} editing={editing} disabled={disabled} onChanged={() => {}}>
      <ul>
        <MovableMember user={user} sdwt={sdwt} location="tree"><span>테스트 구성원</span></MovableMember>
      </ul>
      <SdwtDropTarget sdwt={sdwt} selected={false} onSelect={() => {}}>SDWT-A</SdwtDropTarget>
    </MemberMoveProvider>,
  )
}

describe("조직 보기·편집", () => {
  it("보기는 이름과 노드를 표시하면서 드래그 등록과 이동 핸들을 생략한다", () => {
    const html = render(false)
    expect(html).toContain("테스트 구성원")
    expect(html).toContain("SDWT-A")
    expect(html).not.toContain("소속 이동")
    expect(useDraggable).not.toHaveBeenCalled()
    expect(useDroppable).not.toHaveBeenCalled()
  })

  it("편집을 켜면 구성원과 SDWT를 등록하고 이동 핸들을 표시한다", () => {
    const html = render(true)
    expect(html).toContain('aria-label="테스트 구성원 소속 이동"')
    expect(useDraggable).toHaveBeenCalledTimes(1)
    expect(useDroppable).toHaveBeenCalledTimes(1)
  })

  it("편집 중이어도 조회·이동 처리 중에는 드래그와 드롭을 막는다", () => {
    render(true, true)
    expect(useDraggable).toHaveBeenCalledWith(expect.objectContaining({ disabled: true }))
    expect(useDroppable).toHaveBeenCalledWith(expect.objectContaining({ disabled: true }))
  })
})
