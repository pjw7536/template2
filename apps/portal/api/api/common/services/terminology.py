# =============================================================================
# 모듈 설명: AI prompt가 영문 업무 용어를 canonical 표기로 유지하도록 안내합니다.
# - 주요 대상: Assistant와 Observer의 system prompt
# - 불변 조건: 설명 문장은 한국어로 작성해도 지정 영문 용어는 음역하지 않습니다.
# =============================================================================

"""AI 응답에서 공유하는 영문 업무 용어 보존 규칙입니다."""

ENGLISH_DOMAIN_TERMS_PROMPT = """[영문 업무 용어 보존 규칙]
- 설명 문장은 한국어로 작성하되 영문 업무 용어는 번역하거나 한글로 음역하지 마세요.
- 아래 canonical 표기의 철자, 띄어쓰기와 대소문자를 그대로 사용하세요.
- 사용자 입력이나 업무 데이터에 다른 표기가 있어도 사용자에게 보여 주는 설명에서는 canonical 표기를 사용하세요.
- 영문 업무 용어에 한국어 조사를 붙일 수 있지만 영문 표기 자체를 바꾸지 마세요.

canonical 표기:
- interlock
- wafer
- lot
- wafer lot
- sample wafer
- production wafer
- recipe
- step
- sensor
- offline

금지 표기 예시:
- 인터록, 인터락
- 웨이퍼, 로트, 웨이퍼 로트
- 샘플 웨이퍼, 프로덕션 웨이퍼
- 레시피, 스텝, 센서, 오프라인"""


def append_english_domain_terms_prompt(message: str) -> str:
    """기본 system prompt 뒤에 공통 영문 업무 용어 규칙을 결합합니다."""

    return f"{message.rstrip()}\n\n{ENGLISH_DOMAIN_TERMS_PROMPT}"


__all__ = [
    "ENGLISH_DOMAIN_TERMS_PROMPT",
    "append_english_domain_terms_prompt",
]
