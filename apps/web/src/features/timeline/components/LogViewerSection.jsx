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
        <h2 className="text-md font-bold text-foreground">
          📊 Log Viewer
        </h2>
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <span className="text-muted-foreground">EQPID 바로조회</span>
          <input
            type="checkbox"
            checked={isDirectQuery}
            onChange={(e) => handleToggleChange(e.target.checked)}
            className="h-4 w-4 rounded text-primary focus:ring-primary"
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
              className="flex-1 h-8 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
            />
            <button
              onClick={handleDirectQuery}
              disabled={isLoading || !inputEqpId.trim()}
              className="h-8 whitespace-nowrap rounded-lg bg-primary px-4 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
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
