"""Assistant service constants."""

from __future__ import annotations

DEFAULT_NUM_DOCS = 5
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 30
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_SYSTEM_MESSAGE = "항상 한국어로 대답하는 친절한 AI"
NO_CONTEXT_MESSAGE = "※ 검색된 배경지식이 없습니다. 일반적인 지식을 바탕으로 답변해주세요."
DEFAULT_DUMMY_REPLY = "개발용 더미 응답입니다. 질문({question})을 받아 임시로 답변합니다."
DEFAULT_DUMMY_CONTEXTS = [
    "Etch 장비 점검 시 확인해야 할 주요 체크리스트 요약본입니다. 공정 상태, 안전 장비, 로그 기록 점검을 포함합니다.",
    "RAG 개발용 더미 문서: 공정 변경 시 보고 절차와 협업 흐름을 설명합니다.",
]
DEFAULT_DUMMY_DELAY_MS = 0
STRUCTURED_REPLY_SYSTEM_MESSAGE = (
    "너는 반드시 JSON 객체 1개만 출력한다. 마크다운, 코드펜스, 설명 문장, 추가 텍스트는 금지다."
)
DEFAULT_HISTORY_LIMIT = 20
HISTORY_CACHE_TTL = 60 * 60 * 6
DEFAULT_ROOM_ID = "default"
