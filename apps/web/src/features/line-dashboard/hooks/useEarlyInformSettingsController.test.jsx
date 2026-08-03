import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { DUPLICATE_MESSAGE } from "../utils/lineSettingsConfig"
import { useEarlyInformSettingsController } from "./useEarlyInformSettingsController"

vi.mock("../utils/lineSettingsToasts", () => ({
  showCreateToast: vi.fn(),
  showDeleteToast: vi.fn(),
  showRequestErrorToast: vi.fn(),
  showUpdateToast: vi.fn(),
}))

function createControllerProps(overrides = {}) {
  return {
    lineId: "L1",
    entries: [],
    createEntry: vi.fn(),
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
    ...overrides,
  }
}

describe("조기 알림 설정 controller", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("생성 draft를 정규화하고 성공 후 입력을 초기화한다", async () => {
    const props = createControllerProps({
      createEntry: vi.fn().mockResolvedValue({ id: 1 }),
    })
    const { result } = renderHook(() => useEarlyInformSettingsController(props))

    act(() => {
      result.current.handleFormChange("mainStep", " STEP_A ")
      result.current.handleFormChange("customEndStep", " END_A ")
    })
    await act(async () => {
      await result.current.handleCreate({ preventDefault: vi.fn() })
    })

    expect(props.createEntry).toHaveBeenCalledWith({
      mainStep: "STEP_A",
      customEndStep: "END_A",
    })
    expect(result.current.formValues).toEqual({ mainStep: "", customEndStep: "" })
    expect(result.current.isCreating).toBe(false)
  })

  it("중복 생성 오류는 기존 사용자 안내 문구로 변환한다", async () => {
    const duplicateError = Object.assign(new Error("duplicate"), { status: 409 })
    const props = createControllerProps({
      createEntry: vi.fn().mockRejectedValue(duplicateError),
    })
    const { result } = renderHook(() => useEarlyInformSettingsController(props))

    act(() => result.current.handleFormChange("mainStep", "STEP_A"))
    await act(async () => {
      await result.current.handleCreate({ preventDefault: vi.fn() })
    })

    expect(result.current.formError).toBe(DUPLICATE_MESSAGE)
  })

  it("수정 시 달라진 필드만 API 입력에 포함한다", async () => {
    const entry = { id: 7, mainStep: "STEP_A", customEndStep: "END_A" }
    const props = createControllerProps({
      entries: [entry],
      updateEntry: vi.fn().mockResolvedValue(entry),
    })
    const { result } = renderHook(() => useEarlyInformSettingsController(props))

    act(() => {
      result.current.startEditing(entry)
    })
    act(() => {
      result.current.handleEditChange("customEndStep", " END_B ")
    })
    await act(async () => {
      await result.current.handleSave()
    })

    expect(props.updateEntry).toHaveBeenCalledWith({ id: 7, customEndStep: "END_B" })
    expect(result.current.editingId).toBeNull()
    expect(result.current.savingMap).toEqual({})
  })
})
