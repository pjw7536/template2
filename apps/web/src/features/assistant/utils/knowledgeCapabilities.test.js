import { describe, expect, it } from "vitest"

import { getAssistantKnowledgeCapability } from "./knowledgeCapabilities"

describe("getAssistantKnowledgeCapability", () => {
  it("지식 지원 앱은 현재 화면, Portal과 미지원 앱은 자동을 기본값으로 사용한다", () => {
    expect(getAssistantKnowledgeCapability("emails")).toEqual({
      supportsCurrentScope: true,
      defaultMode: "current_app",
    })
    expect(getAssistantKnowledgeCapability("observer").defaultMode).toBe("current_app")
    expect(getAssistantKnowledgeCapability("portal")).toEqual({
      supportsCurrentScope: false,
      defaultMode: "auto",
    })
    expect(getAssistantKnowledgeCapability("voc").defaultMode).toBe("auto")
  })
})
