import { describe, expect, it } from "vitest";

import {
  buildEvidenceTypeFilters,
  buildObserverEvidenceHref,
  clearObserverEvidenceSearch,
  getObserverEvidenceNavigation,
  getObserverScopeSignature,
  matchesObserverEvidence,
} from "./observerEvidence";

describe("Observer AI 근거 이동", () => {
  it("분석 scope와 evidence ID를 복원 가능한 URL로 변환한다", () => {
    const href = buildObserverEvidenceHref(
      {
        eqpId: "EQP-01",
        from: "2026-08-01T00:00:00+09:00",
        to: "2026-08-03T23:59:59+09:00",
        logTypes: ["eqp", "spc-interlock"],
        tipGroups: ["__ALL__"],
      },
      "EQP:EQP-100"
    );
    const url = new URL(href, "http://localhost");
    const navigation = getObserverEvidenceNavigation(url.searchParams);

    expect(url.pathname).toBe("/observer/EQP-01");
    expect(navigation).toEqual({
      evidenceId: "EQP:EQP-100",
      logKey: "eqp",
      from: "2026-08-01",
      to: "2026-08-03",
      logTypes: ["eqp", "spc-interlock"],
      tipGroups: ["__ALL__"],
    });
  });

  it("prefix가 추가된 ID와 원래 prefix를 가진 ID를 모두 매칭한다", () => {
    expect(
      matchesObserverEvidence(
        { id: "EQP-100", sourceId: 7, logType: "EQP" },
        "EQP:EQP-100"
      )
    ).toBe(true);
    expect(
      matchesObserverEvidence(
        { id: "SPC_ITL:23", sourceId: 23, logType: "SPC_ITL" },
        "SPC_ITL:23"
      )
    ).toBe(true);
  });

  it("호기 전환용 search에서 근거 query만 제거한다", () => {
    const search = clearObserverEvidenceSearch(
      "?from=2026-08-01&to=2026-08-03&evidenceId=EQP%3A1" +
        "&analysisLogType=eqp&analysisLogType=tip" +
        "&analysisTipGroup=GROUP-A&view=compact"
    );
    const params = new URLSearchParams(search);

    expect(params.get("from")).toBe("2026-08-01");
    expect(params.get("to")).toBe("2026-08-03");
    expect(params.get("view")).toBe("compact");
    expect(params.has("evidenceId")).toBe(false);
    expect(params.has("analysisLogType")).toBe(false);
    expect(params.has("analysisTipGroup")).toBe(false);
  });

  it("분석 log type만 활성화하고 scope 비교 순서를 정규화한다", () => {
    expect(buildEvidenceTypeFilters(["eqp", "fdc-interlock"])).toMatchObject({
      EQP: true,
      FDC_ITL: true,
      TIP: false,
    });
    expect(
      getObserverScopeSignature({
        eqpId: "eqp-01",
        from: "2026-08-01",
        to: "2026-08-03",
        logTypes: ["tip", "eqp"],
        tipGroups: ["B", "A"],
      })
    ).toBe(
      getObserverScopeSignature({
        eqpId: "EQP-01",
        from: "2026-08-01T00:00:00+09:00",
        to: "2026-08-03T23:59:59+09:00",
        logTypes: ["eqp", "tip"],
        tipGroups: ["A", "B"],
      })
    );
  });
});
