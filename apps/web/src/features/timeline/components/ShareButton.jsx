// src/features/timeline/components/ShareButton.jsx
import React, { useState } from "react";

export default function ShareButton() {
  const [showToast, setShowToast] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const handleShare = async () => {
    const url = window.location.href;

    try {
      if (navigator.share) {
        await navigator.share({
          title: "EQP Timeline",
          text: "타임라인 링크를 공유합니다",
          url: url,
        });
      } else {
        await navigator.clipboard.writeText(url);
        setShowToast(true);
        setTimeout(() => setShowToast(false), 3000);
      }
    } catch (err) {
      console.error("URL 공유 실패:", err);
      const textArea = document.createElement("textarea");
      textArea.value = url;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    }
  };

  return (
    <>
      {/* 부모 div에 relative position 추가 */}
      <div className="relative inline-block">
        <svg
          onClick={handleShare}
          className="w-5 h-5 text-blue-600 hover:text-blue-700 transition-colors cursor-pointer"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
          />
        </svg>

        {/* 툴팁 */}
        {showTooltip && (
          <div className="absolute top-1/2 left-full transform -translate-y-1/2 ml-2 px-2 py-1 text-xs text-white bg-gray-800 rounded-md whitespace-nowrap pointer-events-none">
            URL 복사
            {/* 툴팁 화살표 추가 (선택사항) */}
            <div className="absolute top-1/2 right-full transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-800"></div>
          </div>
        )}
      </div>

      {/* 토스트 메시지 */}
      {showToast && (
        <div className="fixed bottom-4 right-4 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg animate-fade-in z-50">
          URL이 클립보드에 복사되었습니다!
        </div>
      )}
    </>
  );
}
