import { afterEach, describe, expect, it, vi } from "vitest";

import { observerApi } from "./observerApi";

describe("Observer API", () => {
  afterEach(() => vi.restoreAllMocks());

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
