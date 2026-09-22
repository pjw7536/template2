import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { RouteLoadingFallback } from "./RouteLoadingFallback"

describe("RouteLoadingFallback", () => {
  it("route chunk를 기다리는 동안 접근 가능한 상태를 표시한다", () => {
    render(<RouteLoadingFallback />)

    expect(screen.getByRole("status")).toHaveTextContent("화면을 불러오는 중입니다.")
  })
})
