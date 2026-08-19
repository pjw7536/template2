"""Observer TKIN Prevent selector입니다."""

from ._shared import *  # noqa: F403


def list_tkin_prevent_prc_groups(*, user_sdwt_prod: str) -> List[Dict[str, str]]:
    """m_tkin_prevent 조회에 사용할 PRC 그룹 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값

    반환:
    - List[Dict[str, str]]: PRC 그룹 option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(user_sdwt_prod=user_sdwt_prod)
    rows = _fetch_all(
        """
        select distinct
            prc_group_lookup as id
        from station_master
        where sdwt_prod_lookup = %s
          and prc_group_lookup is not null
          and trim(prc_group_lookup) <> ''
        order by prc_group_lookup
        """,
        [filters["user_sdwt_prod"]],
    )

    return [
        _build_text_record(row, (("id", "id"), ("name", "id")))
        for row in rows
        if row.get("id") is not None
    ]


def _target_tkin_eqp_cte() -> str:
    """m_tkin_prevent 조회 대상 eqp 목록 CTE를 반환합니다."""

    return """
        with target_eqp as (
            select distinct
                station.ch_main as eqp_id
            from station_master station
            where station.sdwt_prod_lookup = %s
              and station.prc_group_lookup = %s
              and station.ch_main is not null
              and station.ch_main <> ''
        )
    """


def _tkin_scope_params(
    *,
    user_sdwt_prod: str,
    prc_group: str,
) -> List[object]:
    """m_tkin_prevent scope 필터 파라미터를 정규화합니다."""

    filters = _normalize_filters(
        user_sdwt_prod=user_sdwt_prod,
        prc_group=prc_group,
    )
    return [filters["user_sdwt_prod"], filters["prc_group"]]


def _tkin_registration_level_clause() -> str:
    """TIP 상태 조회 대상 registration_level 조건을 반환합니다."""

    placeholders = ", ".join(["%s"] * len(TKIN_PREVENT_REGISTRATION_LEVELS))
    return f"and prevent.registration_level in ({placeholders})"


def _tkin_registration_level_params() -> List[object]:
    """TIP 상태 조회 대상 registration_level 파라미터를 반환합니다."""

    return list(TKIN_PREVENT_REGISTRATION_LEVELS)


def _build_tkin_option(row: Row, field_name: str) -> Dict[str, str]:
    """dropdown option 응답을 생성합니다."""

    return _build_text_record(row, (("id", field_name), ("name", field_name)))


def list_tkin_prevent_processes(
    *,
    user_sdwt_prod: str,
    prc_group: str,
) -> List[Dict[str, str]]:
    """m_tkin_prevent process_id 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹

    반환:
    - List[Dict[str, str]]: process_id option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select distinct
            prevent.process_id as process_id
        from m_tkin_prevent prevent
        join target_eqp
          on prevent.eqp_id = target_eqp.eqp_id
        where prevent.process_id is not null
          and prevent.process_id <> ''
          {_tkin_registration_level_clause()}
        order by prevent.process_id
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            *_tkin_registration_level_params(),
        ],
    )
    return [
        _build_tkin_option(row, "process_id")
        for row in rows
        if row.get("process_id") is not None
    ]


def list_tkin_prevent_step_seqs(
    *,
    user_sdwt_prod: str,
    prc_group: str,
    process_id: str,
) -> List[Dict[str, str]]:
    """m_tkin_prevent step_seq 목록을 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹
    - process_id: process_id

    반환:
    - List[Dict[str, str]]: step_seq option 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    process_key = normalize_id(process_id)
    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select distinct
            prevent.step_seq as step_seq
        from m_tkin_prevent prevent
        join target_eqp
          on prevent.eqp_id = target_eqp.eqp_id
        where prevent.process_id = %s
          and prevent.step_seq is not null
          and prevent.step_seq <> ''
          {_tkin_registration_level_clause()}
        order by prevent.step_seq
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            process_key,
            *_tkin_registration_level_params(),
        ],
    )
    return [
        _build_tkin_option(row, "step_seq")
        for row in rows
        if row.get("step_seq") is not None
    ]


def _format_tkin_count(value: object) -> str:
    """float count 값을 화면 표시용 문자열로 변환합니다."""

    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_tkin_status(row: Row) -> str:
    """m_tkin_prevent row를 matrix cell 표시값으로 변환합니다."""

    prevent_type = normalize_id(_safe_text(row.get("tkin_prevent_type")))
    registration_level = _safe_text(row.get("registration_level")).strip()
    registration_level_key = normalize_id(registration_level)
    restrc_lot_count = _format_tkin_count(row.get("tkin_restrc_lot_count"))
    lot_count = _format_tkin_count(row.get("tkin_lot_count"))

    if prevent_type == "DOING":
        return "DOING"

    if prevent_type == "PREVENT":
        level_label = registration_level or "PREVENT"
        if registration_level_key in TKIN_PREVENT_LEVEL2_NAMES:
            level2_count = _format_tkin_count(row.get("level2_restrc_lot_count"))
            return f"{level_label}({level2_count}/{restrc_lot_count}/{lot_count})"
        return f"{level_label}({restrc_lot_count}/{lot_count})"

    return prevent_type or "-"


def get_tkin_prevent_matrix(
    *,
    user_sdwt_prod: str,
    prc_group: str,
    process_id: str,
    step_seq: str,
) -> Dict[str, object]:
    """m_tkin_prevent matrix 데이터를 반환합니다.

    입력:
    - user_sdwt_prod: account_affiliation.user_sdwt_prod에서 선택한 값
    - prc_group: PRC 그룹
    - process_id: process_id
    - step_seq: step_seq

    반환:
    - Dict[str, object]: columns/rows/cell payload

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(process_id=process_id, step_seq=step_seq)
    rows = _fetch_all(
        f"""
        {_target_tkin_eqp_cte()}
        select
            prevent.ppid,
            prevent.line_id,
            prevent.eqp_id,
            prevent.tkin_prevent_chamber_id,
            prevent.tkin_prevent_type,
            prevent.tkin_prevent_comment,
            prevent.registration_level,
            prevent.tkin_restrc_lot_count,
            prevent.tkin_lot_count,
            prevent.level2_restrc_lot_count
        from m_tkin_prevent prevent
        join target_eqp
          on prevent.eqp_id = target_eqp.eqp_id
        where prevent.process_id = %s
          and prevent.step_seq = %s
          and prevent.ppid is not null
          and prevent.ppid <> ''
          {_tkin_registration_level_clause()}
        order by prevent.ppid, prevent.line_id, prevent.eqp_id, prevent.tkin_prevent_chamber_id
        """,
        [
            *_tkin_scope_params(user_sdwt_prod=user_sdwt_prod, prc_group=prc_group),
            filters["process_id"],
            filters["step_seq"],
            *_tkin_registration_level_params(),
        ],
    )

    columns_by_id: Dict[str, Dict[str, str]] = {}
    rows_by_ppid: Dict[str, Dict[str, object]] = {}
    seen_values: Dict[tuple[str, str], set[str]] = {}

    for row in rows:
        ppid = _safe_text(row.get("ppid")).strip()
        line_id = _safe_text(row.get("line_id")).strip()
        eqp_id = _safe_text(row.get("eqp_id")).strip()
        chamber_id = _safe_text(row.get("tkin_prevent_chamber_id")).strip() or "-"
        if not ppid or not eqp_id:
            continue

        column_id = f"{line_id}::{eqp_id}::{chamber_id}"
        column_label = f"{eqp_id}-{chamber_id}"
        columns_by_id.setdefault(
            column_id,
            {
                "id": column_id,
                "lineId": line_id,
                "eqpId": eqp_id,
                "chamberId": chamber_id,
                "label": column_label,
            },
        )
        matrix_row = rows_by_ppid.setdefault(ppid, {"ppid": ppid, "cells": {}})
        cells = matrix_row["cells"]
        if not isinstance(cells, dict):
            continue

        cell_key = (ppid, column_id)
        seen_values.setdefault(cell_key, set())
        status = _format_tkin_status(row)
        comment = _safe_text(row.get("tkin_prevent_comment")).strip()
        seen_key = f"{status}\0{comment}"
        if seen_key in seen_values[cell_key]:
            continue
        seen_values[cell_key].add(seen_key)
        cells.setdefault(column_id, []).append(
            {
                "status": status,
                "comment": comment,
                "type": _safe_text(row.get("tkin_prevent_type")),
                "registrationLevel": _safe_text(row.get("registration_level")),
            }
        )

    return {
        "columns": list(columns_by_id.values()),
        "rows": list(rows_by_ppid.values()),
        "totalRows": len(rows_by_ppid),
        "totalColumns": len(columns_by_id),
    }

__all__ = [
    'list_tkin_prevent_prc_groups',
    '_target_tkin_eqp_cte',
    '_tkin_scope_params',
    '_tkin_registration_level_clause',
    '_tkin_registration_level_params',
    '_build_tkin_option',
    'list_tkin_prevent_processes',
    'list_tkin_prevent_step_seqs',
    '_format_tkin_count',
    '_format_tkin_status',
    'get_tkin_prevent_matrix',
]
