import { describe, expect, it } from "vitest"

import {
  buildMappingLineOptions,
  buildMappingValueLineLabels,
  buildTargetMappingKey,
  findMappingDefaultOption,
  getMappingLineOptionValues,
  parseRecipientSearchTerms,
} from "./lineSettingsMappings"

describe("Line Dashboard 매핑 옵션", () => {
  it("현재 라인을 우선 배치하고 다른 라인의 빈 값과 중복을 제거한다", () => {
    const options = buildMappingLineOptions({
      currentLineId: " L2 ",
      currentValues: ["USER_B", " USER_B ", ""],
      lineRows: [
        { lineId: "L3", userSdwtProds: ["USER_C"] },
        { lineId: "L1", userSdwtProds: ["USER_A"] },
        { lineId: "l2", userSdwtProds: ["SHOULD_IGNORE"] },
      ],
    })

    expect(options).toEqual([
      { lineId: "L2", values: ["USER_B"] },
      { lineId: "L1", values: ["USER_A"] },
      { lineId: "L3", values: ["USER_C"] },
    ])
    expect(getMappingLineOptionValues(options, "l1")).toEqual(["USER_A"])
  })

  it("선호값은 대소문자를 무시해 찾고 없으면 첫 옵션을 사용한다", () => {
    expect(findMappingDefaultOption(["USER_A", "User_B"], "user_b")).toBe("User_B")
    expect(findMappingDefaultOption(["USER_A"], "missing")).toBe("USER_A")
    expect(findMappingDefaultOption([], "missing")).toBe("")
  })

  it("다른 라인 값의 라벨과 canonical mapping key를 만든다", () => {
    expect(buildMappingValueLineLabels([
      { lineId: "L1", userSdwtProds: ["LOCAL"] },
      { lineId: "L2", userSdwtProds: ["REMOTE"] },
    ], "l1")).toEqual({ remote: "L2" })
    expect(buildTargetMappingKey({ userSdwtProd: " User_A ", sdwtProd: " SDWT_A " }))
      .toBe("user_a::sdwt_a")
  })

  it("쉼표 종류를 구분하지 않고 수신인 검색어를 정리한다", () => {
    expect(parseRecipientSearchTerms(" alpha, beta， ,gamma ")).toEqual([
      "alpha",
      "beta",
      "gamma",
    ])
  })
})
