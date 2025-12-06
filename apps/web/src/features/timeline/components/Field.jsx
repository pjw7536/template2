// src/features/timeline/components/logDetail/Field.jsx
import React from "react";
import StreamingText from "./StreamingText";

/**
 * 필드 공통 출력 컴포넌트
 */
export default function Field({
  label,
  value,
  className = "",
  streaming = false,
}) {
  return (
    <>
      <div
        className={`font-semibold text-foreground ${className}`}
      >
        {label}
      </div>
      <div>
        {streaming ? <StreamingText text={value || "-"} /> : value || "-"}
      </div>
    </>
  );
}
