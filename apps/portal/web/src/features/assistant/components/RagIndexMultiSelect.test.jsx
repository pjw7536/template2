import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { RagIndexMultiSelect } from "./RagIndexMultiSelect"

afterEach(cleanup)

it("전체 권한 사용자는 목록에 없는 SDWT를 직접 선택한다", () => {
  const onChange = vi.fn()
  render(<RagIndexMultiSelect label="권한 그룹" values={["A"]} options={["A"]} allowCustomValues onChange={onChange} />)
  fireEvent.change(screen.getByLabelText("권한 그룹 직접 입력"), { target: { value: "New-SDWT" } })
  fireEvent.click(screen.getByRole("button", { name: "추가" }))
  expect(onChange).toHaveBeenCalledWith(["A", "New-SDWT"])
})

it("일반 사용자는 지정된 선택지만 사용한다", () => {
  render(<RagIndexMultiSelect label="권한 그룹" values={["A"]} options={["A"]} onChange={vi.fn()} />)
  expect(screen.queryByLabelText("권한 그룹 직접 입력")).toBeNull()
})
