import { observerApiClient } from "./client";

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
