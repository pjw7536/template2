import { describe, expect, it } from "vitest"

import {
  getRecipientKey,
  mergeRecipientUsers,
  normalizeEntry,
  normalizeUserSdwt,
} from "./lineSettings"
import { validateStepDraft } from "./lineSettingsValidation"

describe("Line Dashboard 설정 정규화", () => {
  it("소속 후보의 공백과 중복을 제거하면서 순서를 유지한다", () => {
    expect(normalizeUserSdwt([" ETCH_A ", "", "ETCH_A", "PHOTO_A"])).toEqual([
      "ETCH_A",
      "PHOTO_A",
    ])
  })

  it("snake_case 설정 응답을 화면 entry 계약으로 변환한다", () => {
    expect(normalizeEntry({
      ID: 7,
      line_id: "L1",
      main_step: "100",
      custom_end_step: 200,
      updated_by: "user@example.com",
    })).toEqual(expect.objectContaining({
      id: "7",
      lineId: "L1",
      mainStep: "100",
      customEndStep: "200",
      updatedBy: "user",
    }))
  })

  it("가입 사용자와 외부 수신인을 canonical key로 병합한다", () => {
    const merged = mergeRecipientUsers(
      [{ userId: 3, displayName: "기존" }],
      [
        { userId: 3, displayName: "갱신" },
        { recipientType: "external", externalKnoxId: "OUTSIDE" },
      ],
    )

    expect(merged).toHaveLength(2)
    expect(merged.map(getRecipientKey).sort()).toEqual(["external:outside", "user:3"])
    expect(merged.find((user) => getRecipientKey(user) === "user:3")?.displayName).toBe("갱신")
  })

  it("step draft는 공백을 정리하고 필수 main step을 검증한다", () => {
    expect(validateStepDraft({ mainStep: " ", customEndStep: "200" })).toEqual({
      error: "Main step is required",
    })
    expect(validateStepDraft({ mainStep: " 100 ", customEndStep: " 200 " })).toEqual({
      normalizedMainStep: "100",
      normalizedCustom: "200",
      error: null,
    })
  })
})
