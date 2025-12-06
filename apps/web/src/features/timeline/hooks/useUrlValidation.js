// src/features/timeline/hooks/useUrlValidation.js
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { timelineApi } from "../api/timelineApi";

export function useUrlValidation(
  params,
  lineId,
  eqpId,
  setLine,
  setSdwt,
  setPrcGroup,
  setEqp
) {
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [isUrlInitialized, setIsUrlInitialized] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    const validateAndSetParams = async () => {
      // URL에 eqpId만 있는 경우
      if (params.eqpId && !params.lineId) {
        setIsValidating(true);
        setValidationError(null);
        setIsUrlInitialized(true);

        try {
          // eqpId로만 조회
          const eqpInfo = await timelineApi.fetchEquipmentInfoByEqpId(
            params.eqpId
          );

          if (!eqpInfo) {
            setValidationError("유효하지 않은 EQP ID입니다.");
            setTimeout(() => navigate("/timeline"), 1500);
            return;
          }

          // 상태 업데이트
          setLine(eqpInfo.lineId);
          setSdwt(eqpInfo.sdwtId);
          setPrcGroup(eqpInfo.prcGroup);
          setEqp(params.eqpId);
        } catch {
          setValidationError("데이터 검증 중 오류가 발생했습니다.");
          setTimeout(() => navigate("/timeline"), 1500);
        } finally {
          setIsValidating(false);
        }
      } else {
        setIsUrlInitialized(true);
      }
    };

    if (!isUrlInitialized) {
      validateAndSetParams();
    }
  }, [
    params.eqpId,
    isUrlInitialized,
    navigate,
    setLine,
    setSdwt,
    setPrcGroup,
    setEqp,
  ]);

  return { isValidating, validationError, isUrlInitialized };
}
