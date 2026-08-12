import { useEffect, useState } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    mergedLogs: [
      {
        id: "TIP-EQP-1-1",
        sourceId: 1,
        logType: "TIP",
        eventTime: "2026-08-01T00:00:00+09:00",
      },
    ],
    logsLoading: false,
    hasMoreByType: {},
    loadingMoreTypes: new Set(),
    residentLimitReached: false,
    loadMoreType: vi.fn(),
  },
  evidenceQuery: {
    data: null,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  },
}));

vi.mock("../store/useObserverSelectionStore", () => ({
  useObserverSelectionStore: () => mockStates.selection,
}));

vi.mock("../store/useObserverStore", () => ({
  useObserverStore: () => mockStates.observer,
}));

vi.mock("./useObserverLogs", () => ({
  useObserverLogs: (_eqpId, typeFilters) => {
    const mergedLogs = mockStates.logs.mergedLogs.filter(
      (log) => typeFilters?.[log.logType]
    );
    return {
      ...mockStates.logs,
      mergedLogs,
      tableData: mergedLogs.map((log) => ({ id: log.id })),
    };
  },
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

vi.mock("./useObserverEvidenceLogQuery", () => ({
  useObserverEvidenceLogQuery: () => mockStates.evidenceQuery,
}));

vi.mock("./useEquipmentInfoQuery", () => ({
  useEquipmentInfoQuery: (eqpId, options = {}) => ({
    data: options.enabled
      ? {
          lineId: `LINE-${eqpId}`,
          sdwtId: `SDWT-${eqpId}`,
          prcGroup: `PRC-${eqpId}`,
        }
      : null,
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
  const routeEqpId = location.pathname.split("/").filter(Boolean)[1];
  const state = useObserverPageState({ eqpId: routeEqpId });
  const range = buildLogDateRangeOptions(state.settings.logRange);

  useEffect(() => {
    setLocationChangeCount((count) => count + 1);
  }, [location.search]);

  return (
    <>
      <button type="button" onClick={() => navigate(evidenceHref)}>
        근거 열기
      </button>
      <button
        type="button"
        onClick={() =>
          state.filters.handleFilterChange({
            target: { name: "TIP", checked: false },
          })
        }
      >
        TIP 필터 해제
      </button>
      <output aria-label="현재 경로">{location.pathname}</output>
      <output aria-label="현재 조회 범위">{`${range.from}~${range.to}`}</output>
      <output aria-label="현재 검색 조건">{location.search}</output>
      <output aria-label="검색 조건 변경 횟수">{locationChangeCount}</output>
      <output aria-label="현재 로그 필터">
        {JSON.stringify(state.filters.typeFilters)}
      </output>
      <output aria-label="근거 이동 상태">
        {state.evidenceNavigationStatus?.status || ""}
      </output>
      <output aria-label="선택된 로그">
        {state.selectedLog?.id || ""}
      </output>
      <output aria-label="표시 로그 목록">
        {state.logs.tableData.map((row) => row.id).join(",")}
      </output>
    </>
  );
}

describe("useObserverPageState 조회 범위 동기화", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStates.selection.eqpId = "EQP-1";
    mockStates.selection.selectedRow = null;
    mockStates.selection.source = null;
    mockStates.selection.setEqp.mockImplementation((eqpId) => {
      mockStates.selection.eqpId = eqpId;
    });
    mockStates.selection.setSelectedRow.mockImplementation((rowId, source) => {
      mockStates.selection.selectedRow = rowId;
      mockStates.selection.source = source;
    });
    mockStates.logs.mergedLogs = [
      {
        id: "TIP-EQP-1-1",
        sourceId: 1,
        logType: "TIP",
        eventTime: "2026-08-01T00:00:00+09:00",
      },
    ];
    mockStates.evidenceQuery.data = null;
    mockStates.evidenceQuery.isFetching = false;
    mockStates.evidenceQuery.isError = false;
    mockStates.evidenceQuery.error = null;
  });

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

  it("근거 이동 시 기존 로그 필터를 유지하고 근거 유형만 활성화한다", async () => {
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=TIP%3ATIP-EQP-1-1&analysisLogType=eqp";

    const view = render(
      <MemoryRouter initialEntries={["/observer/EQP-1"]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );
    const rendered = within(view.container);

    fireEvent.click(rendered.getByRole("button", { name: "TIP 필터 해제" }));
    expect(rendered.getByLabelText("현재 로그 필터")).toHaveTextContent(
      '"TIP":false'
    );
    fireEvent.click(rendered.getByRole("button", { name: "근거 열기" }));

    await waitFor(() => {
      const filters = rendered.getByLabelText("현재 로그 필터");
      expect(filters).toHaveTextContent('"TIP":true');
      expect(filters).toHaveTextContent('"SPC_ITL":true');
      expect(rendered.getByLabelText("근거 이동 상태")).toHaveTextContent(
        "found"
      );
    });
  });

  it("다른 호기를 조회 중이어도 과거 근거 링크의 호기로 한 번만 전환한다", async () => {
    const initialFrom = getDaysBeforeToday(2);
    const initialTo = getDaysBeforeToday(1);
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=TIP%3ATIP-EQP-1-1&analysisLogType=tip";
    mockStates.selection.eqpId = "EQP-2";

    const view = render(
      <MemoryRouter
        initialEntries={[
          `/observer/EQP-2?from=${initialFrom}&to=${initialTo}`,
        ]}
      >
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );
    const rendered = within(view.container);

    fireEvent.click(rendered.getByRole("button", { name: "근거 열기" }));

    await waitFor(() => {
      expect(rendered.getByLabelText("현재 경로")).toHaveTextContent(
        "/observer/EQP-1"
      );
      expect(rendered.getByLabelText("현재 검색 조건")).toHaveTextContent(
        "evidenceId=TIP%3ATIP-EQP-1-1"
      );
      expect(
        rendered.getByLabelText("검색 조건 변경 횟수")
      ).toHaveTextContent("2");
      expect(mockStates.selection.eqpId).toBe("EQP-1");
    });
  });

  it("보존 목록 밖 과거 근거를 복원해 목록과 상세에 표시한다", async () => {
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=EQP%3AEQP-OLD&analysisLogType=eqp";
    mockStates.logs.mergedLogs = [];
    mockStates.evidenceQuery.data = {
      id: "EQP-OLD",
      logType: "EQP",
      eventType: "DOWN",
      eventTime: `${evidenceFrom}T10:00:00+09:00`,
      operator: "USER-1",
      comment: "과거 분석 근거",
    };

    const view = render(
      <MemoryRouter initialEntries={[evidenceHref]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );
    const rendered = within(view.container);

    await waitFor(() => {
      expect(mockStates.selection.setSelectedRow).toHaveBeenCalledWith(
        "EQP-OLD",
        "assistant"
      );
      expect(rendered.getByLabelText("선택된 로그")).toHaveTextContent(
        "EQP-OLD"
      );
      expect(
        rendered.getByLabelText("표시 로그 목록")
      ).toHaveTextContent("EQP-OLD");
      expect(rendered.getByLabelText("근거 이동 상태")).toHaveTextContent(
        "found"
      );
    });
  });

  it("근거 로그 자동 선택 후 Timeline의 사용자 선택을 다시 덮어쓰지 않는다", async () => {
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=TIP%3ATIP-EQP-1-1&analysisLogType=tip";

    const view = render(
      <MemoryRouter initialEntries={[evidenceHref]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockStates.selection.setSelectedRow).toHaveBeenCalledWith(
        "TIP-EQP-1-1",
        "assistant"
      );
    });
    expect(mockStates.selection.setSelectedRow).toHaveBeenCalledTimes(1);

    mockStates.selection.selectedRow = "TIP-EQP-1-2";
    mockStates.selection.source = "observer";
    view.rerender(
      <MemoryRouter initialEntries={[evidenceHref]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockStates.selection.setSelectedRow).toHaveBeenCalledTimes(1);
    });
  });

  it("다른 호기로 전환하면 날짜 범위만 유지하고 AI 근거 안내를 제거한다", async () => {
    const evidenceFrom = getDaysBeforeToday(11);
    const evidenceTo = getDaysBeforeToday(9);
    const evidenceHref =
      `/observer/EQP-1?from=${evidenceFrom}&to=${evidenceTo}` +
      "&evidenceId=TIP%3ATIP-EQP-1-1&analysisLogType=tip" +
      "&analysisTipGroup=GROUP-A";
    const view = render(
      <MemoryRouter initialEntries={[evidenceHref]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );
    const rendered = within(view.container);

    await waitFor(() => {
      expect(rendered.getByLabelText("근거 이동 상태")).toHaveTextContent(
        "found"
      );
    });

    mockStates.selection.eqpId = "EQP-2";
    view.rerender(
      <MemoryRouter initialEntries={[evidenceHref]}>
        <ObserverRangeHarness evidenceHref={evidenceHref} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(rendered.getByLabelText("현재 검색 조건")).toHaveTextContent(
        `from=${evidenceFrom}&to=${evidenceTo}`
      );
      expect(rendered.getByLabelText("현재 검색 조건")).not.toHaveTextContent(
        "evidenceId"
      );
      expect(rendered.getByLabelText("현재 검색 조건")).not.toHaveTextContent(
        "analysisLogType"
      );
      expect(rendered.getByLabelText("현재 검색 조건")).not.toHaveTextContent(
        "analysisTipGroup"
      );
      expect(rendered.getByLabelText("근거 이동 상태")).toBeEmptyDOMElement();
    });
  });
});
