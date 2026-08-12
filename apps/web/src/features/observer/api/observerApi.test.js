import { afterEach, describe, expect, it, vi } from "vitest";

import { observerApi, readObserverAnalysisStream } from "./observerApi";

function createStreamResponse(chunks) {
  const encoder = new TextEncoder();
  return {
    body: new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
  };
}

describe("Observer 분석 SSE parser", () => {
  afterEach(() => vi.restoreAllMocks());

  it("스트리밍 POST 요청에 JSON Content-Type과 SSE Accept를 함께 전송한다", async () => {
    const payload = {
      analysis: { findings: [] },
      meta: {},
      scope: { eqpId: "EQP-1" },
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: createStreamResponse([
        `event: done\ndata: ${JSON.stringify({ payload })}\n\n`,
      ]).body,
    });

    await observerApi.analyzeLogsStream({
      eqpId: "EQP-1",
      from: "2026-08-01",
      to: "2026-08-03",
      logTypes: ["ctttm"],
      tipGroups: ["__ALL__"],
      question: "분석해줘",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/observer/analysis/stream"),
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
      })
    );
  });

  it("분석 item을 표시용 delta로 전달하고 done payload를 반환한다", async () => {
    const payload = {
      analysis: {
        headline: "DOWN 반복",
        summary: "동일 상태가 반복되었습니다.",
        findings: [],
        recommendedChecks: [],
        limitations: [],
      },
      meta: { analysisModel: "gpt-oss-120b" },
      scope: { eqpId: "EQP-1" },
    };
    const onDelta = vi.fn();
    const response = createStreamResponse([
      'event: meta\ndata: {"provider":"openwebui"}\n\n',
      'event: delta\ndata: {"item":{"type":"headline",',
      '"text":"DOWN 반복"}}\n\n',
      `event: done\ndata: ${JSON.stringify({ payload })}\n\n`,
    ]);

    const result = await readObserverAnalysisStream(response, { onDelta });

    expect(onDelta).toHaveBeenCalledWith("### DOWN 반복\n\n");
    expect(result).toEqual(payload);
  });

  it("done 전에 연결이 끝나면 불완전한 분석으로 거부한다", async () => {
    const response = createStreamResponse([
      'event: delta\ndata: {"item":{"type":"summary","text":"분석 중"}}\n\n',
    ]);

    await expect(readObserverAnalysisStream(response)).rejects.toThrow(
      "완료되기 전에 연결이 종료되었습니다."
    );
  });

  it("근거 단건 조회에 분석 당시 설비·범위·ID를 전달한다", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ id: "EQP-100", logType: "EQP" }),
    });

    await observerApi.fetchEvidenceLog({
      logKey: "eqp",
      eqpId: "EQP-1",
      evidenceId: "EQP:EQP-100",
      from: "2026-08-01",
      to: "2026-08-03",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/api/v1/observer/logs/eqp/evidence?eqpId=EQP-1&" +
          "evidenceId=EQP%3AEQP-100&from=2026-08-01&to=2026-08-03"
      ),
      expect.any(Object)
    );
  });
});
