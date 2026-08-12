import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useObserverAssistantContext } from "./useObserverAssistantContext";

const mocks = vi.hoisted(() => ({
  registerPageContext: vi.fn(),
  clearPageContext: vi.fn(),
  analyzeLogsStream: vi.fn(),
}));

vi.mock("@/lib/assistant/pageContext", () => ({
  usePageAssistantContext: () => ({
    registerPageContext: mocks.registerPageContext,
    clearPageContext: mocks.clearPageContext,
  }),
}));

vi.mock("../api/observerApi", () => ({
  observerApi: {
    analyzeLogsStream: mocks.analyzeLogsStream,
  },
}));

describe("useObserverAssistantContext", () => {
  it("stream callback과 중단 signal을 Observer 분석 API에 전달한다", async () => {
    const payload = {
      analysis: {
        headline: "DOWN 반복",
        summary: "동일 상태가 반복되었습니다.",
        findings: [
          {
            category: "EQP",
            target: "DOWN",
            assessment: "반복 발생",
            evidenceIds: ["EQP:1"],
          },
        ],
        recommendedChecks: [],
        limitations: [],
      },
      meta: { analysisModel: "gpt-oss-120b" },
      scope: {
        eqpId: "EQP-1",
        from: "2026-08-01",
        to: "2026-08-03",
        logTypes: ["eqp"],
        tipGroups: ["__ALL__"],
      },
    };
    mocks.analyzeLogsStream.mockResolvedValue(payload);
    const scope = { ...payload.scope };
    const controller = new AbortController();
    const onDelta = vi.fn();

    renderHook(() => useObserverAssistantContext(scope));
    const pageContext = mocks.registerPageContext.mock.calls.at(-1)[0];
    const result = await pageContext.sendMessage({
      prompt: "원인을 분석해줘",
      history: [],
      roomId: "room-1",
      contextKey: pageContext.key,
      signal: controller.signal,
      onDelta,
    });

    expect(mocks.analyzeLogsStream).toHaveBeenCalledWith(
      expect.objectContaining({
        eqpId: "EQP-1",
        signal: controller.signal,
        onDelta,
      })
    );
    expect(result.reply).toContain("### DOWN 반복");
    expect(result.contextSnapshot.evidence[0].evidenceTargets[0]).toEqual({
      id: "EQP:1",
      href: expect.stringContaining("evidenceId=EQP%3A1"),
    });
  });
});
