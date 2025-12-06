// src/features/timeline/hooks/useUrlSync.js
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function useUrlSync(lineId, eqpId, isValidating, isUrlInitialized) {
  const navigate = useNavigate();

  useEffect(() => {
    if (isValidating || !isUrlInitialized) return;

    const currentPath = window.location.pathname;
    const isParamRoute =
      currentPath.includes("/timeline/") && currentPath.split("/").length > 2;

    if (eqpId) {
      // eqpId만 사용하도록 변경
      const newPath = `/timeline/${eqpId}`;
      if (currentPath !== newPath) {
        navigate(newPath, { replace: true });
      }
    } else {
      if (isParamRoute) {
        navigate("/timeline", { replace: true });
      }
    }
  }, [eqpId, navigate, isValidating, isUrlInitialized]);
}
