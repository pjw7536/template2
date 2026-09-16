import { describe, expect, it } from "vitest"

import {
  buildObserverAssistantContextKey,
  sha256Hex,
} from "./observerAssistantContext"

describe("observerAssistantContext", () => {
  it("표준 SHA-256 해시를 계산한다", () => {
    expect(sha256Hex("abc")).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    )
  })

  it("같은 조회 조건은 배열 순서와 EQP 대소문자에 관계없이 같은 키를 만든다", () => {
    const first = buildObserverAssistantContextKey({
      eqpId: "eqp-alpha",
      from: "2026-08-01T00:00:00+09:00",
      to: "2026-08-03T23:59:59+09:00",
      logTypes: ["tip", "eqp"],
      tipGroups: ["B", "A"],
    })
    const second = buildObserverAssistantContextKey({
      eqpId: "EQP-ALPHA",
      from: "2026-08-01",
      to: "2026-08-03",
      logTypes: ["eqp", "tip"],
      tipGroups: ["A", "B"],
    })

    expect(first).toBe(second)
    expect(first).toMatch(/^observer:v1:[0-9a-f]{64}$/)
  })

  it("큰 scope도 API 제한보다 짧고 조건이 바뀌면 다른 키를 만든다", () => {
    const scope = {
      eqpId: "EQP-ALPHA",
      from: "2026-08-01",
      to: "2026-08-03",
      logTypes: ["eqp", "tip"],
      tipGroups: Array.from({ length: 100 }, (_, index) => `${index}-${"가".repeat(300)}`),
    }
    const first = buildObserverAssistantContextKey(scope)
    const second = buildObserverAssistantContextKey({
      ...scope,
      tipGroups: [...scope.tipGroups, "추가 그룹"],
    })

    expect(first.length).toBeLessThanOrEqual(512)
    expect(first).not.toBe(second)
  })
})
