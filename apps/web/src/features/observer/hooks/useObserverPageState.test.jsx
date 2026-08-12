import { useEffect, useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { buildLogDateRangeOptions } from "../utils/logDateRange";
import { getSeoulCalendarDate } from "../utils/dateUtils";
import { useObserverPageState } from "./useObserverPageState";

const mockStates = vi.hoisted(() => ({
  selection: {
    lineId: "LINE-1",
    sdwtId: "SDWT-1",
    prcGroup: "PRC-1",
    eqpId: "EQP-1",
    setLine: vi.fn(),
    setSdwt: vi.fn(),
    setPrcGroup: vi.fn(),
    setEqp: vi.fn(),
    selectedRow: null,
    source: null,
    setSelectedRow: vi.fn(),
    resetSelection: vi.fn(),
  },
  observer: {
    showLegend: true,
    selectedTipGroups: ["__ALL__"],
    setShowLegend: vi.fn(),
    setSelectedTipGroups: vi.fn(),
  },
  logs: {
    mergedLogs: [],
    logsLoading: false,
    hasMoreByType: {},
    loadingMoreTypes: new Set(),
    residentLimitReached: false,
    loadMoreType: vi.fn(),
  },
}));

vi.mock("../store/useObserverSelectionStore", () => ({
  useObserverSelectionStore: () => mockStates.selection,
}));

vi.mock("../store/useObserverStore", () => ({
  useObserverStore: () => mockStates.observer,
}));

vi.mock("./useObserverLogs", () => ({
  useObserverLogs: () => mockStates.logs,
}));

vi.mock("./useObserverLogDetailQuery", () => ({
  useObserverLogDetailQuery: () => ({
    data: null,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("./useObserverAssistantContext", () => ({
  useObserverAssistantContext: () => {},
}));

vi.mock("./useEquipmentInfoQuery", () => ({
  useEquipmentInfoQuery: () => ({
    data: null,
    isFetching: false,
    isError: false,
    error: null,
  }),
}));

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function getDaysBeforeToday(days) {
  const date = getSeoulCalendarDate();
  date.setUTCDate(date.getUTCDate() - days);
  return formatDate(date);
}

function ObserverRangeHarness({ evidenceHref }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [locationChangeCount, setLocationChangeCount] = useState(0);
  const state = useObserverPageState({ lineId: "LINE-1", eqpId: "EQP-1" });
  const range = buildLogDateRangeOptions(state.settings.logRange);

  useEffect(() => {
    setLocationChangeCount((count) => count + 1);
  }, [location.search]);

  return (
    <>
      <button type="button" onClick={() => navigate(evidenceHref)}>
        근거 열기
      </button>
      <output aria-label="현재 조회 범위">{`${range.from}~${range.to}`}</output>
      <output aria-label="현재 검색 조건">{location.search}</output>
      <output aria-label="검색 조건 변경 횟수">{locationChangeCount}</output>
    </>
  );
}

describe("useObserverPageState 조회 범위 동기화", () => {
  it("근거 링크 범위를 현재 조회에 한 번 반영하고 다시 이전 범위로 되돌리지 않는다", async () => {
    const initialFrom = getDaysBeforeToday(2);
    const initialTo = getDaysBeforeToday(1);
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=EQP%3A1&analysisLogType=eqp";

    render(
      <MemoryRouter
        initialEntries={[
          `/observer/EQP-1?from=${initialFrom}&to=${initialTo}`,
        ]}
      >
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "근거 열기" }));

    await waitFor(() => {
      expect(screen.getByLabelText("현재 조회 범위")).toHaveTextContent(
        `${evidenceFrom}~${evidenceTo}`
      );
      expect(screen.getByLabelText("현재 검색 조건")).toHaveTextContent(
        `from=${evidenceFrom}&to=${evidenceTo}`
      );
      expect(screen.getByLabelText("검색 조건 변경 횟수")).toHaveTextContent("2");
    });
  });
});
