// src/features/timeline/components/logDetail/UrlField.jsx
import React from "react";

/**
 * URL 필드 컴포넌트
 */
export default function UrlField({ url }) {
  if (!url) return null;

  return (
    <>
      <div className="font-semibold text-slate-700 dark:text-slate-200">
        URL
      </div>
      <div>
        <a
          href={url}
          className="text-blue-600 dark:text-blue-400 underline break-all"
          target="_blank"
          rel="noopener noreferrer"
        >
          {url}
        </a>
      </div>
    </>
  );
}
