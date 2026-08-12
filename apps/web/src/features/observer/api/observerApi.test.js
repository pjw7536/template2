import { describe, expect, it, vi } from "vitest";

import { readObserverAnalysisStream } from "./observerApi";

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
});
