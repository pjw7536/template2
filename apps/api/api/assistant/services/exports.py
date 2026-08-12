# =============================================================================
# 모듈: Assistant 대화 내보내기
# 주요 함수: build_assistant_markdown_export, build_assistant_csv_export
# 주요 가정: selector가 현재 활성 분기의 메시지만 전달합니다.
# =============================================================================
"""Assistant 대화를 Markdown과 Excel 호환 CSV byte로 변환합니다."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Sequence

from ..models import AssistantConversation, AssistantMessage

CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _escape_csv_formula(value: object) -> object:
    """스프레드시트가 텍스트 셀을 수식으로 실행하지 않게 보호합니다."""

    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def build_assistant_markdown_export(
    *,
    conversation: AssistantConversation,
    messages: Sequence[AssistantMessage],
) -> bytes:
    """대화방 metadata와 현재 분기를 UTF-8 Markdown으로 반환합니다."""

    lines = [f"# {conversation.title}", ""]
    for message in messages:
        role = "사용자" if message.role == AssistantMessage.Roles.USER else "Assistant"
        lines.extend([f"## {role}", "", message.content, ""])
        snapshot = message.context_snapshot
        if snapshot is not None:
            lines.extend(
                [
                    f"> 분석 문맥: {snapshot.kind} · {snapshot.context_key}",
                    f"> 근거 수: {len(snapshot.evidence or [])}",
                    "",
                ]
            )
    return "\n".join(lines).strip().encode("utf-8")


def build_assistant_csv_export(
    *,
    conversation: AssistantConversation,
    messages: Sequence[AssistantMessage],
) -> bytes:
    """Excel에서 바로 열 수 있는 UTF-8 BOM CSV로 현재 분기를 반환합니다."""

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["대화방", _escape_csv_formula(conversation.title)])
    writer.writerow(["메시지 ID", "역할", "내용", "문맥", "생성 시각", "근거 수"])
    for message in messages:
        snapshot = message.context_snapshot
        writer.writerow(
            [
                _escape_csv_formula(message.client_id),
                "사용자" if message.role == AssistantMessage.Roles.USER else "Assistant",
                _escape_csv_formula(message.content),
                _escape_csv_formula(message.context_key),
                message.created_at.isoformat(),
                len(snapshot.evidence or []) if snapshot is not None else 0,
            ]
        )
    return output.getvalue().encode("utf-8-sig")


__all__ = ["build_assistant_csv_export", "build_assistant_markdown_export"]
