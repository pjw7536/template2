from __future__ import annotations


class AssistantConfigError(RuntimeError):
    """어시스턴트 연동에 필요한 설정이 누락되었을 때 발생합니다.

    Raised when assistant integration is missing required configuration.
    """


class AssistantRequestError(RuntimeError):
    """외부 어시스턴트(RAG/LLM) 호출이 실패했을 때 발생합니다.

    Raised when external assistant call fails.
    """
