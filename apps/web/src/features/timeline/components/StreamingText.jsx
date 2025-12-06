// src/features/timeline/components/logDetail/StreamingText.jsx
import React, { useState, useEffect } from "react";

/**
 * 스트리밍 텍스트 애니메이션 컴포넌트
 */
export default function StreamingText({ text, speed = 30 }) {
  const [displayedText, setDisplayedText] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    setDisplayedText("");
    setCurrentIndex(0);
  }, [text]);

  useEffect(() => {
    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setDisplayedText((prev) => prev + text[currentIndex]);
        setCurrentIndex((prev) => prev + 1);
      }, speed);

      return () => clearTimeout(timer);
    }
  }, [currentIndex, text, speed]);

  return (
    <span className="inline-block">
      {displayedText}
      {currentIndex < text.length && (
        <span className="inline-block w-2 h-4 bg-slate-600 dark:bg-slate-400 animate-pulse ml-0.5" />
      )}
    </span>
  );
}
