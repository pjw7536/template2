import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RoomList } from "./RoomList"

describe("RoomList 상호작용", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it("검색 입력을 debounce하고 다음 page 요청을 전달한다", () => {
    const onSearchRooms = vi.fn()
    const onLoadMore = vi.fn()
    render(
      <RoomList
        rooms={[{ id: "room-1", name: "DOWN 분석" }]}
        activeRoomId="room-1"
        onSearchRooms={onSearchRooms}
        onLoadMore={onLoadMore}
        hasMore
      />,
    )

    act(() => vi.advanceTimersByTime(250))
    expect(onSearchRooms).not.toHaveBeenCalled()

    fireEvent.change(screen.getByPlaceholderText("대화방 검색"), {
      target: { value: "TIP" },
    })
    expect(onSearchRooms).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(250))
    expect(onSearchRooms).toHaveBeenLastCalledWith("TIP")

    fireEvent.click(screen.getByRole("button", { name: "더 불러오기" }))
    expect(onLoadMore).toHaveBeenCalledOnce()
  })

  it("삭제 확인 후에만 대화방 삭제를 실행한다", () => {
    const onDeleteRoom = vi.fn()
    render(
      <RoomList
        rooms={[{ id: "room-1", name: "DOWN 분석" }]}
        activeRoomId="room-1"
        onDeleteRoom={onDeleteRoom}
      />,
    )

    fireEvent.pointerDown(screen.getByRole("button", { name: "DOWN 분석 메뉴" }), {
      button: 0,
      ctrlKey: false,
    })
    fireEvent.click(screen.getByRole("menuitem", { name: "삭제" }))
    expect(screen.getByText("대화방을 삭제할까요?")).toBeInTheDocument()
    expect(onDeleteRoom).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "삭제" }))
    expect(onDeleteRoom).toHaveBeenCalledWith("room-1")
  })

  it("답변 생성 중인 대화방은 삭제하지 못하지만 선택할 수 있다", () => {
    const onSelectRoom = vi.fn()
    render(
      <RoomList
        rooms={[{ id: "room-1", name: "DOWN 분석" }]}
        activeRoomId="room-2"
        onSelectRoom={onSelectRoom}
        disabledRoomIds={["room-1"]}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /DOWN 분석생성 중/ }))
    expect(onSelectRoom).toHaveBeenCalledWith("room-1")
    expect(screen.getByRole("button", { name: "DOWN 분석 메뉴" })).toBeDisabled()
  })

  it("현재 목록의 삭제 가능한 대화방을 전체 선택해 한 번에 삭제한다", async () => {
    const onDeleteRooms = vi.fn().mockResolvedValue({
      deletedIds: ["room-1", "room-2"],
      failedIds: [],
    })
    render(
      <RoomList
        rooms={[
          { id: "room-1", name: "DOWN 분석" },
          { id: "room-2", name: "TIP 분석" },
          { id: "room-3", name: "생성 중 대화" },
        ]}
        activeRoomId="room-1"
        disabledRoomIds={["room-3"]}
        onDeleteRooms={onDeleteRooms}
      />,
    )

    const selectionButton = screen.getByRole("button", { name: "선택" })
    expect(selectionButton.parentElement).toHaveClass("h-9")
    fireEvent.click(selectionButton)
    expect(screen.getByRole("checkbox", { name: "생성 중 대화 선택" })).toBeDisabled()
    const selectAllButton = screen.getByRole("button", { name: "전체 선택" })
    expect(selectAllButton.parentElement).toHaveClass("h-9")
    fireEvent.click(selectAllButton)
    expect(screen.getByText("2개 선택")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "삭제" }))
    expect(screen.getByText("선택한 대화방을 삭제할까요?")).toBeInTheDocument()
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "2개 삭제" }))
    })

    expect(onDeleteRooms).toHaveBeenCalledWith(["room-1", "room-2"])
    expect(screen.queryByText("2개 선택")).not.toBeInTheDocument()
  })
})
