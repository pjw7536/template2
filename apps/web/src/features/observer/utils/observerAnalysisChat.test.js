import { describe, expect, it } from "vitest";

import {
  buildObserverAnalysisQuestion,
  formatObserverAnalysisChatReply,
  formatObserverAnalysisStreamItem,
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

  it("구조화 결과에서 분석 내용만 ChatWidget markdown 메시지로 변환한다", () => {
    const reply = formatObserverAnalysisChatReply({
      analysis: {
        headline: "DOWN 반복 발생",
        summary: "압력 관련 상태를 확인해야 합니다.",
        findings: [
          {
            category: "EQP",
            target: "DOWN",
            assessment:
              "3건이 짧은 시간대에 집중되어 개별 작업보다 공통 설비 조건의 영향 가능성이 큽니다.",
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
    expect(reply).toContain("#### 주요 분석");
    expect(reply).toContain("**EQP · DOWN**");
    expect(reply).toContain("공통 설비 조건의 영향 가능성이 큽니다.");
    expect(reply).toContain("> 분석 한계: 인과관계는 추정입니다.");
    expect(reply).not.toContain("Pressure alarm");
    expect(reply).not.toContain("SPC interlock 인접");
    expect(reply).not.toContain("EQP:1");
    expect(reply).not.toContain("압력 센서 확인");
    expect(reply).not.toContain("분석 범위:");
    expect(reply).not.toContain("분석 입력:");
    expect(reply).not.toContain("분석 버전:");
  });

  it("주요 분석과 분석 한계를 간결한 상한으로 제한한다", () => {
    const reply = formatObserverAnalysisChatReply({
      analysis: {
        findings: Array.from({ length: 6 }, (_, index) => ({
          category: "EQP",
          target: `상태-${index + 1}`,
          assessment: `분석-${index + 1}`,
        })),
        limitations: ["한계-1", "한계-2", "한계-3", "한계-4"],
      },
    });

    expect(reply).toContain("분석-5");
    expect(reply).not.toContain("분석-6");
    expect(reply).toContain("한계-3");
    expect(reply).not.toContain("한계-4");
  });

  it("스트리밍 항목도 분석 내용만 단계적으로 표시한다", () => {
    const summary = formatObserverAnalysisStreamItem({
      type: "summary",
      text: "DOWN이 특정 시간대에 집중됐습니다.",
    });
    const finding = formatObserverAnalysisStreamItem({
      type: "finding",
      category: "CORRELATION",
      target: "DOWN-SPC",
      assessment: "SPC Interlock이 반복적으로 선행해 연관 가능성이 있습니다.",
      recordedCauses: ["Pressure alarm"],
      inferredCauses: ["SPC 인접"],
      evidenceIds: ["EQP:1"],
    });
    const checks = formatObserverAnalysisStreamItem({
      type: "recommendedChecks",
      values: ["센서 확인"],
    });
    const limitations = formatObserverAnalysisStreamItem({
      type: "limitations",
      values: ["인과관계는 추정입니다.", "한계-2", "한계-3", "한계-4"],
    });

    expect(summary).toContain("#### 주요 분석");
    expect(finding).toContain("**CORRELATION · DOWN-SPC**");
    expect(finding).toContain("연관 가능성이 있습니다.");
    expect(finding).not.toContain("Pressure alarm");
    expect(finding).not.toContain("SPC 인접");
    expect(finding).not.toContain("EQP:1");
    expect(checks).toBe("");
    expect(limitations).toContain("> 분석 한계: 인과관계는 추정입니다.");
    expect(limitations).not.toContain("한계-4");
  });
});
