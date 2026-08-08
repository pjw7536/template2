import { useState } from "react"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { moveAppById } from "../utils/appOrder"
import { AppList } from "./AppList"

afterEach(cleanup)

const APPS = [
  { id: 1, name: "첫 번째 앱", category: "DX App", viewCount: 0, likeCount: 0, commentCount: 0 },
  { id: 2, name: "두 번째 앱", category: "Engineer App", viewCount: 0, likeCount: 0, commentCount: 0 },
  { id: 3, name: "세 번째 앱", category: "Etch Report", viewCount: 0, likeCount: 0, commentCount: 0 },
]

function renderEditableList(onMoveApp) {
  render(
    <AppList
      apps={APPS}
      selectedAppId={null}
      onSelect={vi.fn()}
      onOpenLink={vi.fn()}
      isLoading={false}
      isOrderEditing
      isOrderSaving={false}
      onMoveApp={onMoveApp}
    />,
  )
}

function StatefulEditableList() {
  const [apps, setApps] = useState(APPS)

  return (
    <AppList
      apps={apps}
      selectedAppId={null}
      onSelect={vi.fn()}
      onOpenLink={vi.fn()}
      isLoading={false}
      isOrderEditing
      isOrderSaving={false}
      onMoveApp={(sourceAppId, targetAppId) => {
        setApps((current) => moveAppById(current, sourceAppId, targetAppId))
      }}
    />
  )
}

describe("AppList 순서 편집", () => {
  it("카드를 다른 카드에 드래그하면 해당 위치 이동을 요청한다", () => {
    const onMoveApp = vi.fn()
    const dataTransfer = {
      effectAllowed: "none",
      dropEffect: "none",
      setData: vi.fn(),
    }
    renderEditableList(onMoveApp)

    fireEvent.dragStart(screen.getByLabelText("세 번째 앱, 현재 순서 3"), { dataTransfer })
    fireEvent.dragEnter(screen.getByLabelText("첫 번째 앱, 현재 순서 1"), { dataTransfer })

    expect(onMoveApp).toHaveBeenCalledWith(3, 1)
  })

  it("화살표 키로 인접한 카드 위치 이동을 요청한다", () => {
    const onMoveApp = vi.fn()
    renderEditableList(onMoveApp)

    fireEvent.keyDown(screen.getByLabelText("두 번째 앱, 현재 순서 2"), {
      key: "ArrowLeft",
    })

    expect(onMoveApp).toHaveBeenCalledWith(2, 1)
  })

  it("앱을 맨 앞으로 옮기면 기존 앱을 모두 한 칸씩 뒤로 민다", () => {
    const dataTransfer = {
      effectAllowed: "none",
      dropEffect: "none",
      setData: vi.fn(),
    }
    render(<StatefulEditableList />)

    fireEvent.dragStart(screen.getByLabelText("세 번째 앱, 현재 순서 3"), { dataTransfer })
    fireEvent.dragEnter(screen.getByLabelText("첫 번째 앱, 현재 순서 1"), { dataTransfer })

    expect(screen.getAllByRole("listitem").map((item) => item.getAttribute("aria-label"))).toEqual([
      "세 번째 앱, 현재 순서 1",
      "첫 번째 앱, 현재 순서 2",
      "두 번째 앱, 현재 순서 3",
    ])
  })
})
