"""ct_process_comment 요약 prompt와 원천 text 변환을 제공합니다."""

from __future__ import annotations

import re
from datetime import datetime

SUMMARY_CHUNK_MAX_EVENTS = 40
SUMMARY_CHUNK_MAX_CHARS = 8000
CONTENTS_EVENT_HEADER_PATTERN = re.compile(
    r"^\[\s*(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*/\s*(?P<author>[^\]]+?)\s*\]\s*$"
)

SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 요약기입니다.
입력으로 제공된 이벤트 목록에 실제로 포함된 사실만 사용하세요.
workorder_title은 사람이 작성한 작업 제목 또는 작업 목적 설명입니다.
workorder_title이 제공되면 이벤트 의미를 파악하는 보조 정보로 반영하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

작업:
1. 설비 점검 이력을 확인 가능한 시간 순서대로 정리하세요.
2. 입력 이벤트는 모두 출력하되, 각 시간 이벤트의 내용만 한 줄로 짧게 요약하세요.
3. 이벤트 설명은 핵심 상태나 조치만 남기고 가능하면 35자 이내로 쓰세요.
4. 각 줄은 반드시 "[YYYY-MM-DD HH:MM] 이벤트" 형식으로 쓰세요.
5. 한 줄에는 하나의 이벤트만 쓰고, 이벤트 사이에는 줄바꿈만 사용하세요.
6. 대괄호 안 시간은 입력 이벤트의 시간을 그대로 사용하세요.
7. 입력 이벤트끼리 합치거나 누락하지 마세요.
8. 같은 시간 이벤트 안에서 같은 의미의 중복 내용만 합치세요.
9. 출력 형식 외의 설명, 추론 과정, 사과문, 안내문은 쓰지 마세요.

출력 형식:
[2026-06-19 13:44] 점검 시작
[2026-06-19 18:37] 조치 완료"""

CORE_SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심 요약기입니다.
입력으로 제공된 시간순 요약에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

작업:
1. 입력된 시간순 요약 전체 흐름을 1~2문장으로 매우 짧게 요약하세요.
2. 시간순 요약이 한 줄이거나 단순 점검/확인/알람 내용이어도 확인된 사실을 그대로 짧게 요약하세요.
3. 문제가 해결, 완료, 정상화, 복구되었다는 표현은 입력에 명시된 경우에만 쓰세요.
4. 입력에 해결 여부가 명시되지 않았다면 확인된 진행 상황만 있는 그대로 요약하세요.
5. 단순 점검, 확인, 조치 진행, 알람 확인만으로 문제가 해결되었다고 추정하지 마세요.
6. 구체 장비명, 부품명, 알람명, 작업명, 상태, 결과가 있으면 우선 포함하세요.
7. 구체 대상이 없어도 입력에 있는 일반 표현만으로 짧게 요약할 수 있으면 "NO_CORE_SUMMARY"를 쓰지 마세요.
8. 입력이 비어 있거나 내용 없음, 확인 불가, 해당 없음처럼 저장할 사실이 없을 때만 정확히 "NO_CORE_SUMMARY"를 출력하세요.
9. 핵심요약을 작성할 때 첫 줄은 반드시 "핵심 요약: "으로 시작하세요.
10. 출력은 핵심 요약 한 줄 또는 "NO_CORE_SUMMARY"만 작성하세요.
11. 설명, 추론 과정, 사과문, 안내문, markdown은 쓰지 마세요.

출력 형식:
핵심 요약: 점검 시작 후 알람을 확인했고 조치 내용이 기록되었습니다."""

CORE_SUMMARY_REVIEW_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심요약 검수자입니다.
입력으로 시간순 요약과 후보 핵심요약이 제공됩니다.
시간순 요약에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

판단 기준:
1. 후보 핵심요약이 시간순 요약의 사실과 충돌하지 않으면 단순하거나 일반적인 표현이어도 "KEEP"만 출력하세요.
2. 후보가 모호하지만 시간순 요약에서 더 구체적으로 바꿀 수 있으면 "REWRITE: " 뒤에 구체 핵심요약을 한 줄로 작성하세요.
3. 후보가 시간순 요약에 없는 사실을 추가했거나 시간순 요약에 저장할 사실이 없을 때만 정확히 "NO_CORE_SUMMARY"를 출력하세요.
4. 해결, 완료, 정상화, 복구 표현은 시간순 요약에 명시된 경우에만 쓰세요.
5. 판단이 애매하면 버리지 말고 "KEEP"을 출력하세요.
6. 설명, 추론 과정, 사과문, 안내문, markdown은 쓰지 마세요.

출력 형식:
KEEP
REWRITE: TMP 센서 알람 후 CH-A 밸브 탈착 및 장착이 완료되었습니다.
NO_CORE_SUMMARY"""

def _normalize_summary_source_text(value: str) -> str:
    """이스케이프된 개행을 복원하고 연속된 줄바꿈을 하나로 축약합니다."""

    normalized = (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return re.sub(r"\n(?:[ \t]*\n)+", "\n", normalized).strip()


def _build_timestamped_event_text(
    contents_text: str,
    *,
    default_event_time: datetime | None = None,
) -> str:
    """comment header 또는 기본 시간으로 timestamp 확정 이벤트를 생성합니다."""

    events: list[str] = []
    current_time = ""
    current_lines: list[str] = []

    def flush_current_event() -> None:
        if not current_time or not current_lines:
            return
        event_text = " ".join(" ".join(current_lines).split())
        if event_text:
            events.append(f"[{current_time}] {event_text}")

    for raw_line in contents_text.splitlines():
        line = raw_line.strip()
        match = CONTENTS_EVENT_HEADER_PATTERN.match(line)
        if match:
            flush_current_event()
            current_time = match.group("time")
            current_lines = []
            continue
        if current_time and line:
            current_lines.append(line)

    flush_current_event()
    if events or default_event_time is None:
        return "\n".join(events)

    if not contents_text:
        return ""
    return f"[{default_event_time.strftime('%Y-%m-%d %H:%M')}] {contents_text}"


def _split_summary_source_chunks(source_text: str) -> list[str]:
    """큰 요약 입력을 OpenWebUI가 처리하기 쉬운 이벤트 묶음으로 나눕니다."""

    lines = [line for line in source_text.splitlines() if line.strip()]
    if not lines:
        return []

    chunks: list[str] = []
    current_lines: list[str] = []
    current_chars = 0

    for line in lines:
        projected_chars = current_chars + len(line) + (1 if current_lines else 0)
        should_flush = bool(current_lines) and (
            len(current_lines) >= SUMMARY_CHUNK_MAX_EVENTS or projected_chars > SUMMARY_CHUNK_MAX_CHARS
        )
        if should_flush:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_chars = 0

        current_lines.append(line)
        current_chars += len(line) + (1 if len(current_lines) > 1 else 0)

    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def _build_summary_prompt_from_source(
    *,
    source_label: str,
    prompt_source: str,
    workorder_title: str = "",
) -> list[dict[str, str]]:
    """요약 source를 OpenWebUI chat completions용 message 목록으로 감쌉니다."""

    content_parts: list[str] = []
    if workorder_title.strip():
        content_parts.extend(
            [
                "workorder_title:",
                "<<<",
                workorder_title.strip(),
                ">>>",
                "",
            ]
        )
    content_parts.extend(
        [
            f"{source_label}:",
            "<<<",
            prompt_source,
            ">>>",
        ]
    )

    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(content_parts),
        },
    ]


def build_summary_prompt(
    contents_text: str,
    workorder_title: str = "",
    default_event_time: datetime | None = None,
) -> list[dict[str, str]]:
    """OpenWebUI chat completions용 고정 message 목록을 생성합니다."""

    normalized_contents_text = _normalize_summary_source_text(contents_text)
    timestamped_events = _build_timestamped_event_text(
        normalized_contents_text,
        default_event_time=default_event_time,
    )
    return _build_summary_prompt_from_source(
        source_label="timestamped_events" if timestamped_events else "contents_text",
        prompt_source=timestamped_events or normalized_contents_text,
        workorder_title=workorder_title,
    )


def build_core_summary_prompt(event_summary: str) -> list[dict[str, str]]:
    """시간순 요약 결과를 핵심 요약 생성용 message 목록으로 변환합니다."""

    return [
        {"role": "system", "content": CORE_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "time_ordered_summary:",
                    "<<<",
                    event_summary,
                    ">>>",
                ]
            ),
        },
    ]


def build_core_summary_review_prompt(event_summary: str, core_summary: str) -> list[dict[str, str]]:
    """핵심 요약 후보를 검수하는 OpenWebUI message 목록을 생성합니다."""

    return [
        {"role": "system", "content": CORE_SUMMARY_REVIEW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "time_ordered_summary:",
                    "<<<",
                    event_summary,
                    ">>>",
                    "",
                    "candidate_core_summary:",
                    "<<<",
                    core_summary,
                    ">>>",
                ]
            ),
        },
    ]

__all__ = [
    "_build_summary_prompt_from_source",
    "_build_timestamped_event_text",
    "_normalize_summary_source_text",
    "_split_summary_source_chunks",
    "build_core_summary_prompt",
    "build_core_summary_review_prompt",
    "build_summary_prompt",
]
