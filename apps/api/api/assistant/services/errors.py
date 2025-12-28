# =============================================================================
# 모듈: 어시스턴트 서비스 예외 정의
# 주요 클래스: AssistantConfigError, AssistantRequestError
# 주요 가정: 상위 레이어에서 예외를 잡아 HTTP 오류로 변환합니다.
# =============================================================================
from __future__ import annotations


class AssistantConfigError(RuntimeError):
    """어시스턴트 연동에 필요한 설정이 누락되었을 때 발생합니다."""


class AssistantRequestError(RuntimeError):
    """외부 어시스턴트(RAG/LLM) 호출이 실패했을 때 발생합니다."""
