"""Observer line, SDWT, 설비 메타데이터 selector입니다."""

from ._shared import *  # noqa: F403


def list_lines() -> List[Dict[str, str]]:
    """Drone target 기준으로 Observer에서 선택 가능한 라인 목록을 반환합니다.

    입력:
    - 없음

    반환:
    - List[Dict[str, str]]: 라인 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    payload = drone_selectors.get_tip_status_line_sdwt_options_payload()
    rows = payload.get("lines") if isinstance(payload, dict) else []
    return [
        {"id": line_id, "name": line_id}
        for row in rows
        if isinstance(row, dict)
        for line_id in [_safe_text(row.get("lineId")).strip()]
        if line_id
    ]


def list_sdwt_for_line(*, line_id: str) -> List[Dict[str, str]]:
    """Drone target line 기준으로 station_master에 존재하는 user_sdwt_prod 목록을 반환합니다.

    입력:
    - line_id: 라인 ID

    반환:
    - List[Dict[str, str]]: SDWT 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(line_id=line_id)
    line_key = filters["line_id"]
    payload = drone_selectors.get_tip_status_line_sdwt_options_payload()
    rows = payload.get("lines") if isinstance(payload, dict) else []
    matched_line = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and normalize_id(_safe_text(row.get("lineId"))) == line_key
        ),
        {},
    )
    values = matched_line.get("userSdwtProds") if isinstance(matched_line, dict) else []

    return [
        {
            "id": value,
            "name": value,
            "lineId": line_key,
        }
        for raw_value in values
        for value in [_safe_text(raw_value).strip()]
        if value
    ]


def list_prc_groups(*, line_id: str, sdwt_id: str) -> List[Dict[str, str]]:
    """라인/SDWT 조합 기준 PRC 그룹 목록을 반환합니다.

    입력:
    - line_id: 라인 ID
    - sdwt_id: SDWT ID(설비/공정 식별자)

    반환:
    - List[Dict[str, str]]: PRC 그룹 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(line_id=line_id, sdwt_id=sdwt_id)
    sdwt_key = filters["sdwt_id"]
    if not _find_drone_target_for_sdwt(
        sdwt_id=sdwt_key,
        preferred_line_id=filters["line_id"],
    ):
        return []

    rows = _fetch_all(
        """
        select distinct
            prc_group as id
        from station_master
        where sdwt_prod_lookup = %s
          and prc_group is not null
        order by prc_group
        """,
        [sdwt_key],
    )

    return [
        _build_text_record(row, (("id", "id"), ("name", "id")))
        for row in rows
        if row.get("id") is not None
    ]


def list_equipments(
    *,
    line_id: str,
    sdwt_id: str,
    prc_group: str,
) -> List[Dict[str, str]]:
    """라인/SDWT/PRC 조합 기준 설비 목록을 반환합니다.

    입력:
    - line_id: 라인 ID
    - sdwt_id: SDWT ID(설비/공정 식별자)
    - prc_group: PRC 그룹 코드

    반환:
    - List[Dict[str, str]]: 설비 목록

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(
        line_id=line_id,
        sdwt_id=sdwt_id,
        prc_group=prc_group,
    )
    target = _find_drone_target_for_sdwt(
        sdwt_id=filters["sdwt_id"],
        preferred_line_id=filters["line_id"],
    )
    if not target:
        return []

    sdwt_key = filters["sdwt_id"]
    prc_key = filters["prc_group"]
    sql = """
        select distinct on (station.station)
            station.station as id,
            %s as line_id,
            station.sdwt_prod as sdwt_prod,
            station.prc_group as prc_group
        from station_master station
        where station.prc_group_lookup = %s
          and station.station is not null
    """
    params: List[object] = [target["lineId"], prc_key]

    if sdwt_key:
        sql += " and station.sdwt_prod_lookup = %s"
        params.append(sdwt_key)

    sql += " order by station.station"
    rows = _fetch_all(sql, params)

    equipments: List[Dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in rows:
        eqp_id = row.get("id")
        if eqp_id is None:
            continue
        normalized_eqp_id = str(eqp_id)
        if normalized_eqp_id in seen_ids:
            continue
        seen_ids.add(normalized_eqp_id)
        equipments.append(
            _build_text_record(
                row,
                (
                    ("id", "id"),
                    ("lineId", "line_id"),
                    ("sdwtId", "sdwt_prod"),
                    ("prcGroup", "prc_group"),
                    ("name", "id"),
                ),
            )
        )
    return equipments


def get_equipment_info(*, eqp_id: str, line_id: str = "") -> Dict[str, str] | None:
    """eqpId 기준 설비 메타데이터를 반환합니다.

    입력:
    - eqp_id: 설비 ID
    - line_id: Drone target line ID(선택)

    반환:
    - Dict[str, str] | None: 설비 메타데이터(없으면 None)

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    filters = _normalize_filters(eqp_id=eqp_id, line_id=line_id)
    eqp_key = filters["eqp_id"]
    row = _fetch_one(
        """
        select distinct
            station.station as id,
            station.sdwt_prod as sdwt_prod,
            station.sdwt_prod_lookup as sdwt_prod_lookup,
            station.prc_group as prc_group
        from station_master station
        where station.station_lookup = %s
        limit 1
        """,
        [eqp_key],
    )

    if not row:
        return None

    target = _find_drone_target_for_sdwt(
        sdwt_id=_safe_text(row.get("sdwt_prod_lookup") or row.get("sdwt_prod")),
        preferred_line_id=filters["line_id"],
    )
    if not target:
        return None

    return {
        "id": _safe_text(row.get("id")),
        "lineId": target["lineId"],
        "sdwtId": target["sdwtId"],
        "prcGroup": _safe_text(row.get("prc_group")),
    }

__all__ = [
    'list_lines',
    'list_sdwt_for_line',
    'list_prc_groups',
    'list_equipments',
    'get_equipment_info',
]
