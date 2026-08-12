import { describe, expect, it } from "vitest";

import {
  buildObserverAnalysisQuestion,
  formatObserverAnalysisChatReply,
} from "./observerAnalysisChat";

describe("observerAnalysisChat", () => {
  it("현재 질문과 최근 사용자/Assistant 대화를 분석 질문으로 구성한다", () => {
    const question = buildObserverAnalysisQuestion("왜 반복됐어?", [
      { role: "assistant", content: "이전 답변" },
      { role: "user", content: "DOWN을 분석해줘" },
      { role: "user", content: "왜 반복됐어?" },
    ]);

    expect(question).toContain("왜 반복됐어?");
    expect(question).toContain("DOWN을 분석해줘");
    expect(question).toContain("이전 답변");
  });

  it("분석 질문을 backend 계약과 같은 2,400자로 제한한다", () => {
    const question = buildObserverAnalysisQuestion("가".repeat(3000));

    expect(question).toHaveLength(2400);
  });

  it("구조화 분석 결과를 ChatWidget markdown 메시지로 변환한다", () => {
    const reply = formatObserverAnalysisChatReply({
      analysis: {
        headline: "DOWN 반복 발생",
        summary: "압력 관련 상태를 확인해야 합니다.",
        findings: [
          {
            category: "EQP",
            target: "DOWN",
            assessment: "3회 발생했습니다.",
            recordedCauses: ["Pressure alarm"],
            inferredCauses: ["SPC interlock 인접"],
            evidenceIds: ["EQP:1"],
          },
        ],
        recommendedChecks: ["압력 센서 확인"],
        limitations: ["인과관계는 추정입니다."],
      },
      meta: {
        eqpTargetCount: 3,
        tipTargetCount: 1,
        contextIncludedCount: 2,
        analysisModel: "gpt-oss-120b",
        promptVersion: "observer-analysis-prompt-v1",
      },
      scope: { eqpId: "EQP-1", from: "2026-08-01T00:00:00+09:00", to: "2026-08-03T23:59:59+09:00" },
    });

    expect(reply).toContain("### DOWN 반복 발생");
    expect(reply).toContain("**기록된 원인**");
    expect(reply).toContain("압력 센서 확인");
    expect(reply).toContain("EQP-1 · 2026-08-01 ~ 2026-08-03");
    expect(reply).toContain("분석 버전: gpt-oss-120b · observer-analysis-prompt-v1");
  });
});
