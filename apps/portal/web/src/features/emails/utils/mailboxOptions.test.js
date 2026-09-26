import { expect, it } from "vitest"
import { buildAffiliationOptions } from "./mailboxOptions"

it("Line 목록 없이도 접근 가능한 SDWT를 모두 선택할 수 있다", () => {
  const options = buildAffiliationOptions({ lines: [] }, ["A", "B", "__sent__"])
  expect(options.map((option) => option.id)).toEqual(["A", "B"])
  expect(options[0]).toMatchObject({ label: "A", lineId: null })
})

it("알려진 소속만 Line을 표시하고 권한 없는 소속은 제외한다", () => {
  const options = buildAffiliationOptions({ lines: [{ lineId: "L1", userSdwtProds: ["A", "Denied"] }] }, ["A", "Other-SDWT"])
  expect(options.map((option) => option.id)).toEqual(["A", "Other-SDWT"])
  expect(options[0].label).toBe("L1 / A")
})
