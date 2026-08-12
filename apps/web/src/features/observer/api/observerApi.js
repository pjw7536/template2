import { observerApiClient } from "./client";
import { formatObserverAnalysisStreamItem } from "../utils/observerAnalysisChat";

function parseSseBlock(block) {
  const lines = block.split("\n");
  const event =
    lines.find((line) => line.startsWith("event:"))?.slice(6).trim() ||
    "message";
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return { event, payload: {} };
  try {
    return { event, payload: JSON.parse(data) };
  } catch {
    throw new Error("Observer 스트리밍 응답 형식이 올바르지 않습니다.");
  }
}

export async function readObserverAnalysisStream(response, { onDelta } = {}) {
  const reader = response.body?.getReader?.();
  if (!reader) throw new Error("브라우저가 스트리밍 응답을 지원하지 않습니다.");

  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;
  let didReceiveDone = false;

  const handleBlock = (block) => {
    const { event, payload } = parseSseBlock(block);
    if (event === "delta") {
      const content = formatObserverAnalysisStreamItem(payload?.item);
      if (content) onDelta?.(content);
      return;
    }
    if (event === "done") {
      didReceiveDone = true;
      finalPayload = payload?.payload;
      return;
    }
    if (event === "error") {
      throw new Error(payload?.error || "Observer 분석 스트리밍에 실패했습니다.");
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        if (block) handleBlock(block);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    const trailingBlock = buffer.trim();
    if (trailingBlock) handleBlock(trailingBlock);
  } finally {
    reader.releaseLock?.();
  }

  if (!didReceiveDone || !finalPayload || typeof finalPayload !== "object") {
    throw new Error("Observer 분석 응답이 완료되기 전에 연결이 종료되었습니다.");
  }
  return finalPayload;
}

export const observerApi = {
  // 라인 목록 엔드포인트
  fetchLines: () => observerApiClient("/lines"),

  // SDWT 목록
  fetchSDWT: (lineId) => observerApiClient("/sdwts", { params: { lineId } }),

  // PRC Group 목록
  fetchPrcGroups: (lineId, sdwtId) =>
    observerApiClient("/prc-groups", { params: { lineId, sdwtId } }),

  // Equipment 목록
  fetchEquipments: (lineId, sdwtId, prcGroup) => {
    const params = { lineId };
    if (sdwtId) params.sdwtId = sdwtId;
    if (prcGroup) params.prcGroup = prcGroup;
    return observerApiClient("/equipments", { params });
  },

  // 로그 가져오기 - sdwtId 제거
  fetchLogs: ({ lineId, eqpId, ...logQueryOptions }) =>
    observerApiClient("/logs", {
      params: { lineId, eqpId, ...logQueryOptions },
    }),

  fetchLogBatch: ({ eqpId, types, pageSize = 250, signal, ...range }) =>
    observerApiClient("/logs/page", {
      params: {
        eqpId,
        types: types.join(","),
        pageSize,
        ...range,
      },
      signal,
    }),

  fetchLogPage: ({
    logKey,
    eqpId,
    cursor,
    pageSize = 250,
    signal,
    ...range
  }) =>
    observerApiClient(`/logs/${logKey}/page`, {
      params: { eqpId, cursor, pageSize, ...range },
      signal,
    }),

  fetchLogDetail: ({ logKey, eqpId, detailId, signal }) =>
    observerApiClient(`/logs/${logKey}/detail`, {
      params: { eqpId, logId: detailId },
      signal,
    }),

  analyzeLogs: ({
    eqpId,
    from,
    to,
    logTypes,
    tipGroups,
    question,
    roomId,
    contextKey,
  }) =>
    observerApiClient("/analysis", {
      method: "POST",
      body: JSON.stringify({
        eqpId,
        from,
        to,
        logTypes,
        tipGroups,
        question,
        roomId,
        contextKey,
      }),
      timeout: 130000,
    }),

  analyzeLogsStream: ({
    eqpId,
    from,
    to,
    logTypes,
    tipGroups,
    question,
    roomId,
    contextKey,
    signal,
    onDelta,
  }) =>
    observerApiClient("/analysis/stream", {
      method: "POST",
      headers: { Accept: "text/event-stream" },
      body: JSON.stringify({
        eqpId,
        from,
        to,
        logTypes,
        tipGroups,
        question,
        roomId,
        contextKey,
      }),
      timeout: 130000,
      signal,
      responseParser: (response) =>
        readObserverAnalysisStream(response, { onDelta }),
    }),

  // EQP 정보 조회
  fetchEquipmentInfo: (lineId, eqpId) =>
    observerApiClient(`/equipment-info/${lineId}/${eqpId}`),

  fetchEquipmentInfoByEqpId: (eqpId) =>
    observerApiClient(`/equipment-info/${eqpId}`),

  // tkin Prevent PRC Group 목록
  fetchTkinPreventPrcGroups: ({ userSdwtProd }) =>
    observerApiClient("/tkin-prevent/prc-groups", {
      params: { userSdwtProd },
    }),

  // tkin Prevent process 목록
  fetchTkinPreventProcesses: ({ userSdwtProd, prcGroup }) =>
    observerApiClient("/tkin-prevent/processes", {
      params: { userSdwtProd, prcGroup },
    }),

  // tkin Prevent step_seq 목록
  fetchTkinPreventStepSeqs: ({ userSdwtProd, prcGroup, processId }) =>
    observerApiClient("/tkin-prevent/step-seqs", {
      params: { userSdwtProd, prcGroup, processId },
    }),

  // tkin Prevent matrix 데이터
  fetchTkinPreventMatrix: ({
    userSdwtProd,
    prcGroup,
    processId,
    stepSeq,
  }) =>
    observerApiClient("/tkin-prevent/matrix", {
      params: { userSdwtProd, prcGroup, processId, stepSeq },
    }),
};
