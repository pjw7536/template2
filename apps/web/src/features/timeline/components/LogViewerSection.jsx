// src/features/timeline/components/LogViewerSection.jsx - 개선된 버전
import React, { useState } from "react";
import LineSelector from "./LineSelector";
import SDWTSelector from "./SDWTSelector";
import EqpSelector from "./EqpSelector";
import PrcGroupSelector from "./PrcGroupSelector";
import { timelineApi } from "../api/timelineApi";

export default function LogViewerSection({
  lineId,
  sdwtId,
  prcGroup,
  eqpId,
  setLine,
  setSdwt,
  setPrcGroup,
  setEqp,
}) {
  const [isDirectQuery, setIsDirectQuery] = useState(false);
  const [inputEqpId, setInputEqpId] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // 토글 변경 시 처리
  const handleToggleChange = (checked) => {
    setIsDirectQuery(checked);

    if (checked) {
      // 토글 ON: 모든 선택값 초기화
      setLine("");
      setSdwt("");
      setPrcGroup("");
      setEqp("");
      setInputEqpId("");
    } else {
      // 토글 OFF: 입력값만 초기화
      setInputEqpId("");
    }
  };

  const handleDirectQuery = async () => {
    if (!inputEqpId.trim()) return;

    setIsLoading(true);
    try {
      const eqpInfo = await timelineApi.fetchEquipmentInfoByEqpId(inputEqpId);

      if (eqpInfo) {
        setLine(eqpInfo.lineId);
        setSdwt(eqpInfo.sdwtId);
        setPrcGroup(eqpInfo.prcGroup);
        setEqp(inputEqpId);
      } else {
        alert("유효하지 않은 EQP ID입니다.");
      }
    } catch (error) {
      console.error("EQP 정보 조회 실패:", error);
      alert("EQP 정보 조회에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleDirectQuery();
    }
  };

  return (
    <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-md font-bold text-slate-900 dark:text-white">
          📊 Log Viewer
        </h2>
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <span className="text-slate-600 dark:text-slate-400">
            EQPID 바로조회
          </span>
          <input
            type="checkbox"
            checked={isDirectQuery}
            onChange={(e) => handleToggleChange(e.target.checked)}
            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
          />
        </label>
      </div>

      <div
        className={`grid gap-2 ${
          isDirectQuery ? "grid-cols-[0.8fr_1fr_1fr_1.2fr]" : "grid-cols-4"
        }`}
      >
        {/* Line Selector */}
        <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
          <LineSelector
            lineId={lineId}
            setLineId={isDirectQuery ? () => {} : setLine}
          />
          {isDirectQuery && (
            <div className="absolute inset-0 cursor-not-allowed" />
          )}
        </div>

        {/* SDWT Selector */}
        <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
          <SDWTSelector
            lineId={lineId}
            sdwtId={sdwtId}
            setSdwtId={isDirectQuery ? () => {} : setSdwt}
          />
          {isDirectQuery && (
            <div className="absolute inset-0 cursor-not-allowed" />
          )}
        </div>

        {/* PRC Group Selector */}
        <div className={`relative ${isDirectQuery ? "opacity-50" : ""}`}>
          <PrcGroupSelector
            lineId={lineId}
            sdwtId={sdwtId}
            prcGroup={prcGroup}
            setPrcGroup={isDirectQuery ? () => {} : setPrcGroup}
          />
          {isDirectQuery && (
            <div className="absolute inset-0 cursor-not-allowed" />
          )}
        </div>

        {isDirectQuery ? (
          <div className="flex gap-2">
            <input
              type="text"
              value={inputEqpId}
              onChange={(e) => setInputEqpId(e.target.value.toUpperCase())}
              onKeyPress={handleKeyPress}
              placeholder="EQP ID 입력..."
              disabled={isLoading}
              autoFocus
              className="flex-1 px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-xs dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-50 h-8"
            />
            <button
              onClick={handleDirectQuery}
              disabled={isLoading || !inputEqpId.trim()}
              className="px-4 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap h-8"
            >
              {isLoading ? "조회중" : "조회"}
            </button>
          </div>
        ) : (
          <EqpSelector
            lineId={lineId}
            sdwtId={sdwtId}
            prcGroup={prcGroup}
            eqpId={eqpId}
            setEqpId={setEqp}
          />
        )}
      </div>
    </section>
  );
}
