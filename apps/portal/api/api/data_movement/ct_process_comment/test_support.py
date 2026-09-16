"""ct_process_comment 테스트 fixture helper입니다."""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from api.data_movement.ct_process_comment.services import spec
from api.data_movement.ct_process_comment.services import summary as summary_module


def _write_deflate_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_comment_row(
    *,
    workorder_id: str = "WO1",
    line_id: str = "L1",
    eqp_id: str = "EQP1",
    contents: str = "contents",
    use_yn: str = "Y",
    create_date: str = "2999-01-01 00:00:00",
    update_date: str | None = None,
) -> list[str]:
    """DDL 순서에 맞춘 테스트용 comment row를 생성합니다."""

    row = [""] * len(spec.FILE_COLUMNS)
    row[0] = workorder_id
    row[1] = line_id
    row[2] = "PROC"
    row[3] = "1"
    row[4] = "C1"
    row[5] = eqp_id
    row[6] = "N"
    row[7] = contents
    row[8] = "contents text"
    row[9] = create_date
    row[10] = "creator"
    row[11] = update_date or create_date
    row[12] = "updater"
    row[13] = use_yn
    row[14] = "modifier"
    row[15] = create_date
    row[16] = "part"
    return row


def _build_openwebui_session(
    reply: str = "[2026-06-19 13:44] 점검",
    replies: list[str | None] | None = None,
) -> Mock:
    """OpenWebUI 응답을 흉내 내는 requests session mock을 생성합니다."""

    def build_response(content: str | None) -> Mock:
        response = Mock()
        response.headers = {"Content-Type": "application/json"}
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": content,
                    }
                }
            ]
        }
        return response

    session = Mock()
    if replies is not None:
        session.post.side_effect = [build_response(content) for content in replies]
    else:
        session.post.return_value = build_response(reply)
    return session


def _build_openwebui_json_session(resp_json: Any) -> Mock:
    """지정한 JSON을 반환하는 OpenWebUI session mock을 생성합니다."""

    response = Mock()
    response.headers = {"Content-Type": "application/json"}
    response.raise_for_status.return_value = None
    response.json.return_value = resp_json
    session = Mock()
    session.post.return_value = response
    return session


def _build_openwebui_config() -> summary_module.OpenWebUISummaryConfig:
    """테스트용 OpenWebUI 설정 객체를 생성합니다."""

    return summary_module.OpenWebUISummaryConfig(
        url="https://openwebui.example.local/v1/chat/completions",
        model="test-model",
        api_token="test-token",
        timeout_seconds=3,
    )
