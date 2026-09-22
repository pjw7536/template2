"""Observer 로그 source adapter와 직렬화 규약입니다."""

from ._shared import *  # noqa: F403


def _fetch_eqp_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return eqp_status_chg_selectors.fetch_eqp_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


def _fetch_tip_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return mi_tip_update_hist_selectors.fetch_tip_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


def _build_interlock_log_item(
    row: Row,
    *,
    log_type: str,
) -> Dict[str, object]:
    """m_interlock 원천 행을 Observer 공통 로그와 상세 필드로 변환합니다."""

    source_id = row.get("id")
    event_time = row.get("event_time")
    interlock_no = _safe_text(row.get("interlock_no")).strip()
    interlock_type = _safe_text(row.get("interlock_type")).strip()
    interlock_kind = _safe_text(row.get("interlock_kind")).strip().upper()
    event_type = interlock_no or interlock_type or interlock_kind
    comment = (
        _safe_text(row.get("interlock_comment")).strip()
        or _safe_text(row.get("interlock_desc")).strip()
        or _safe_text(row.get("engr_comment")).strip()
    )

    return {
        "id": f"{log_type}:{source_id}",
        "sourceId": source_id,
        "logType": log_type,
        "eventType": event_type,
        "eventTime": _serialize_event_time(event_time),
        "operator": None,
        "comment": comment,
        "interlockKind": interlock_kind,
        "lineId": row.get("line_id"),
        "interlockNo": row.get("interlock_no"),
        "itemValue": row.get("item_value"),
        "interlockType": row.get("interlock_type"),
        "interlockComment": row.get("interlock_comment"),
        "ppid": row.get("ppid"),
        "usl": row.get("usl"),
        "specTarget": row.get("spec_target"),
        "lsl": row.get("lsl"),
        "ucl": row.get("ucl"),
        "cl": row.get("cl"),
        "lcl": row.get("lcl"),
        "batchId": row.get("batch_id"),
        "metroItem": row.get("metro_item"),
        "interlockDesc": row.get("interlock_desc"),
        "areaName": row.get("area_name"),
        "processId": row.get("process_id"),
        "lotId": row.get("lot_id"),
        "prodStepSeq": row.get("prod_step_seq"),
        "prodProgsTime": row.get("prod_progs_time"),
        "prodEqpType": row.get("prod_eqp_type"),
        "prodBayName": row.get("prod_bay_name"),
        "prodChamberId": row.get("prod_chamber_id"),
        "metroStepSeq": row.get("metro_step_seq"),
        "metroProgsTime": row.get("metro_progs_time"),
        "intlkOccurWeek": row.get("intlk_occur_week"),
        "intlkOccurYearM": row.get("intlk_occur_year_m"),
        "metroEqpId": row.get("metro_eqp_id"),
        "prodEqpId": row.get("prod_eqp_id"),
        "eqpId": row.get("prod_eqp_id"),
        "lastUpdateDate": row.get("last_update_date"),
        "waferId": row.get("wafer_id"),
        "eqpProcessPhase": row.get("eqp_process_phase"),
        "eqpDetailComment": row.get("eqp_detail_comment"),
        "engrComment": row.get("engr_comment"),
    }


def _fetch_interlock_logs(
    *,
    eqp_id: str,
    interlock_kind: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    """SPC/FDC interlock 이력을 종류별 Observer 로그로 반환합니다."""

    kind_key = normalize_id(interlock_kind)
    resolved_start_at = start_at or _period_date()
    rows = m_interlock_selectors.fetch_interlock_timeline_rows(
        eqp_id=eqp_id,
        interlock_kind=kind_key,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )
    log_type = f"{kind_key}_ITL"
    return [
        _build_interlock_log_item(row, log_type=log_type)
        for row in rows
    ]


def _fetch_ctttm_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    base_url = getattr(settings, "DRONE_CTTTM_BASE_URL", "")
    time_clause, time_params = _build_time_clause(
        "workorder.inprg_date",
        start_at=start_at,
        end_at=end_at,
    )
    limit_clause, limit_params = _build_limit_clause(limit)
    rows = _fetch_all_on_default(
        f"""
        select
            workorder.workorder_id as id,
            workorder.eqp_id as eqp_id,
            'CTTTM' as log_type,
            workorder.work_type as event_type,
            workorder.inprg_date as event_time,
            null as operator,
            workorder.description as comment,
            concat(%s, workorder.workorder_id, '&lineId=', workorder.line_id) as url,
            comment.llm_core_summary as core_summary,
            comment.llm_summary as summary
        from ctttm_workorder_list workorder
        left join ct_process_comment comment
          on comment.workorder_id = workorder.workorder_id
        where workorder.eqp_id_lookup = %s
          and {time_clause}
        order by workorder.inprg_date desc
        {limit_clause}
        """,
        [base_url, eqp_id, *time_params, *limit_params],
    )

    return [
        {
            "id": row.get("id"),
            "eqpId": row.get("eqp_id"),
            "logType": row.get("log_type"),
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "comment": row.get("comment"),
            "url": row.get("url"),
            "coreSummary": row.get("core_summary"),
            "summary": row.get("summary"),
        }
        for row in rows
    ]


def _fetch_racb_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    resolved_start_at = start_at or _period_date()
    return racb_list_selectors.fetch_racb_timeline_logs(
        eqp_id=eqp_id,
        start_at=resolved_start_at,
        end_at=end_at,
        limit=limit,
    )


def _unique_sequence(values: Sequence[str]) -> List[str]:
    """입력 순서를 유지하면서 중복 문자열을 제거합니다."""

    seen: set[str] = set()
    return [
        value
        for value in values
        if value and not (value in seen or seen.add(value))
    ]


DEFECT_IMAGE_PATH = "/map/api/map-image/v3/defect-map"
DEFECT_IMAGE_STATIC_PARAMS = {
    "profileid": "DEFAULT",
    "themeid": "DEFAULT",
    "width": "500",
    "height": "500",
    "site": "GH",
    "targetDB": "APP",
    "useCache": "true",
    "includeCoordinate": "false",
}


def _to_http_url(value: object) -> str:
    """URL 값에 프로토콜이 없으면 https 기준 URL로 정규화합니다."""

    if value is None:
        return ""
    url = str(value).strip()
    if not url:
        return ""
    if re.match(r"^https?://", url, flags=re.IGNORECASE):
        return url
    return f"https://{url}"


def _normalize_defect_image_row(value: object) -> int | None:
    """defect map 이미지 행 번호를 정수로 정규화합니다."""

    try:
        selected_row = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return selected_row if selected_row >= 0 else None


def _build_esop_defect_image_urls(entry: Dict[str, object], map_url: str) -> List[str]:
    """ESOP defect_url JSON에서 defect map 이미지 URL 목록을 생성합니다."""

    raw_image_urls = entry.get("image_urls")
    if isinstance(raw_image_urls, list):
        image_urls = [_to_http_url(url) for url in raw_image_urls]
        return [url for url in image_urls if url]

    map_file = str(entry.get("map_file") or "").strip()
    raw_rows = entry.get("image_rows")
    if raw_rows is None:
        raw_rows = entry.get("images_rows")
    if not map_url or not map_file or not isinstance(raw_rows, list):
        return []

    match = re.match(r"^(https?://[^/]+)", map_url, flags=re.IGNORECASE)
    if not match:
        return []

    origin = match.group(1)
    seen_rows: set[int] = set()
    image_urls: List[str] = []
    for raw_row in raw_rows:
        selected_row = _normalize_defect_image_row(raw_row)
        if selected_row is None or selected_row in seen_rows:
            continue
        seen_rows.add(selected_row)

        params = {
            "file": map_file,
            "selected_row": str(selected_row),
            **DEFECT_IMAGE_STATIC_PARAMS,
        }
        query = urlencode(params)
        image_urls.append(f"{origin}{DEFECT_IMAGE_PATH}?{query}")

    return image_urls


def _normalize_esop_defect_maps(value: object) -> List[Dict[str, object]]:
    """ESOP defect_url 저장값을 화면용 링크 목록으로 정규화합니다."""

    if not value:
        return []

    entries: object
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError:
            if not raw.startswith("http"):
                return []
            return [{"label": "Defect Map", "url": raw, "imageUrls": []}]
    else:
        entries = value

    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    maps: List[Dict[str, object]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        url = _to_http_url(entry.get("map_url") or entry.get("url"))
        if not url:
            continue
        label = str(
            entry.get("label") or entry.get("step_seq") or f"Defect Map {index}"
        ).strip()
        maps.append(
            {
                "label": label or f"Defect Map {index}",
                "url": url,
                "imageUrls": _build_esop_defect_image_urls(entry, url),
            }
        )
    return maps


def _build_esop_chamber_filters(eqp_id: str) -> tuple[str, str, List[object]]:
    """ESOP 조회용 기본 설비 ID와 chamber 조건을 구성합니다."""

    if "-" not in eqp_id:
        return eqp_id, "", []

    base_eqp, suffix = eqp_id.split("-", 1)
    digits = re.findall(r"\d", suffix)
    chamber_candidates = _unique_sequence(digits or list(suffix.strip()))
    if not chamber_candidates:
        return base_eqp, "", []

    like_clauses = " or ".join(["sop.chamber_ids like %s"] * len(chamber_candidates))
    return (
        base_eqp,
        f" and ({like_clauses})",
        [f"%{ch}%" for ch in chamber_candidates],
    )


def _fetch_esop_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> List[Dict[str, object]]:
    base_eqp, match_clause, match_params = _build_esop_chamber_filters(eqp_id)
    time_clause, time_params = _build_time_clause(
        "sop.created_at",
        start_at=start_at,
        end_at=end_at,
    )
    limit_clause, limit_params = _build_limit_clause(limit)

    rows = _fetch_all_on_default(
        f"""
        select
            sop.id as id,
            sop.sample_type as event_type,
            sop.created_at as event_time,
            sop.knox_id as operator,
            sop.status as status,
            sop.comment as comment,
            sop.line_id as line_id,
            sop.eqp_id as eqp_id,
            sop.chamber_ids as chamber_ids,
            sop.lot_id as lot_id,
            sop.defect_url as defect_url
        from drone_sop as sop
        where {time_clause}
          and sop.eqp_id_lookup = %s
          {match_clause}
        order by sop.created_at desc
        {limit_clause}
        """,
        [*time_params, base_eqp, *match_params, *limit_params],
    )

    return [
        {
            "id": row.get("id"),
            "logType": "ESOP",
            "eventType": row.get("event_type"),
            "eventTime": row.get("event_time"),
            "operator": row.get("operator"),
            "status": row.get("status"),
            "comment": row.get("comment"),
            "lineId": row.get("line_id"),
            "eqpId": row.get("eqp_id"),
            "eqpCb": f"{row.get('eqp_id') or '-'}-{row.get('chamber_ids') or '-'}",
            "lotId": row.get("lot_id"),
            "defectMaps": _normalize_esop_defect_maps(row.get("defect_url")),
        }
        for row in rows
    ]


def _numeric_detail_id(log_id: str) -> int | None:
    """detail endpoint에서 사용하는 source PK를 양의 정수로 변환합니다."""

    try:
        value = int(str(log_id or "").strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _serialize_eqp_log_detail(row: Row) -> dict[str, object]:
    """EQP source row를 상세 payload로 변환합니다."""

    return {
        "id": f"EQP-{row.get('eqp_event_key')}",
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_cb"),
        "logType": "EQP",
        "eventType": row.get("eqp_status_type"),
        "eventTime": _serialize_event_time(row.get("chg_time")),
        "operator": row.get("operator_emp_id"),
        "comment": row.get("chg_comment"),
        "lineId": row.get("line_id"),
        "eqpCode": row.get("eqp_code"),
        "eqpModeType": row.get("eqp_mode_type"),
        "lastUpdateTime": _serialize_event_time(row.get("last_update_time"))
        if row.get("last_update_time") is not None
        else None,
    }


def _serialize_tip_log_detail(row: Row) -> dict[str, object]:
    """TIP source row를 상세 payload로 변환합니다."""

    register_name = _safe_text(row.get("register_name"))
    return {
        "id": _tip_page_log_id(row),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_cb"),
        "logType": "TIP",
        "eventType": row.get("event_type"),
        "eventTime": _serialize_event_time(row.get("gpm_update_date")),
        "operator": register_name.split("-", 1)[0] or None,
        "comment": row.get("tip_comment"),
        "lineId": row.get("line_id"),
        "process": row.get("process_id"),
        "step": row.get("step_seq"),
        "ppid": row.get("ppid"),
        "reticleId": row.get("reticle_id"),
        "productId": row.get("product_id"),
        "tipType": row.get("tip_type"),
        "tipChangeType": row.get("tip_chg_type"),
        "tipLevel": row.get("tip_level"),
    }


def _serialize_ctttm_log_detail(row: Row) -> dict[str, object]:
    """CTTTM source row와 최신 요약을 상세 payload로 변환합니다."""

    summary = _fetch_one(
        """
        select llm_core_summary, llm_summary
        from ct_process_comment
        where workorder_id = %s
        order by updated_at desc, id desc
        limit 1
        """,
        [row.get("workorder_id")],
    ) or {}
    return {
        "id": row.get("workorder_id"),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_id"),
        "logType": "CTTTM",
        "eventType": row.get("work_type"),
        "eventTime": _serialize_event_time(row.get("inprg_date")),
        "operator": None,
        "comment": row.get("description"),
        "coreSummary": summary.get("llm_core_summary"),
        "summary": summary.get("llm_summary"),
        "lineId": row.get("line_id"),
        "completedAt": _serialize_event_time(row.get("comp_date"))
        if row.get("comp_date") is not None
        else None,
    }


def _serialize_racb_log_detail(row: Row) -> dict[str, object]:
    """RACB source row를 report URL이 포함된 상세 payload로 변환합니다."""
    base_url = str(getattr(settings, "RACB_REPORT_BASE_URL", "") or "").strip()
    query = urlencode(
        {"racbId": row.get("c_racb_id"), "lineId": row.get("line_id") or ""}
    )
    return _serialize_log_time_fields(
        {
            **row,
            "id": f"RACB-{row.get('c_racb_id')}-{row.get('eqp_cb')}",
            "sourceId": row.get("id"),
            "logType": "RACB",
            "eventType": (
                f"{row.get('racb_type_cd') or ''}_{row.get('status_code') or ''}"
            ),
            "eventTime": row.get("update_date"),
            "operator": row.get("create_user"),
            "comment": row.get("title"),
            "url": f"{base_url}?{query}" if base_url else None,
        }
    )


def _serialize_esop_log_detail(row: Row) -> dict[str, object]:
    """ESOP source row와 defect map 정보를 상세 payload로 변환합니다."""

    return {
        "id": row.get("id"),
        "sourceId": row.get("id"),
        "logType": "ESOP",
        "eventType": row.get("sample_type"),
        "eventTime": _serialize_event_time(row.get("created_at")),
        "operator": row.get("knox_id"),
        "status": row.get("status"),
        "comment": row.get("comment"),
        "lineId": row.get("line_id"),
        "eqpId": row.get("eqp_id"),
        "eqpCb": f"{row.get('eqp_id') or '-'}-{row.get('chamber_ids') or '-'}",
        "lotId": row.get("lot_id"),
        "defectMaps": _normalize_esop_defect_maps(row.get("defect_url")),
        "sampleGroup": row.get("sample_group"),
        "sdwtProd": row.get("sdwt_prod"),
        "processId": row.get("proc_id"),
        "ppid": row.get("ppid"),
        "mainStep": row.get("main_step"),
        "metroCurrentStep": row.get("metro_current_step"),
        "metroSteps": row.get("metro_steps"),
        "metroEndStep": row.get("metro_end_step"),
        "ctttmUrls": row.get("ctttm_urls"),
    }


_OBSERVER_LOG_SOURCES: dict[str, _ObserverLogSource] = {
    "eqp": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_eqp_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: eqp_status_chg_selectors.fetch_eqp_timeline_page(
            **options
        ),
        serialize_page_row=serialize_compact_eqp_row,
        cursor_time_field="chg_time",
        fetch_detail=lambda eqp_id, source_id: eqp_status_chg_selectors.get_eqp_timeline_detail(
            eqp_id=eqp_id,
            log_id=str(source_id),
        ),
        serialize_detail_row=_serialize_eqp_log_detail,
    ),
    "tip": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_tip_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: mi_tip_update_hist_selectors.fetch_tip_timeline_page(
            **options
        ),
        serialize_page_row=serialize_compact_tip_row,
        cursor_time_field="gpm_update_date",
        fetch_detail=lambda eqp_id, source_id: mi_tip_update_hist_selectors.get_tip_timeline_detail(
            eqp_id=eqp_id,
            log_id=str(source_id),
        ),
        serialize_detail_row=_serialize_tip_log_detail,
    ),
    "spc-interlock": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_interlock_logs(
            eqp_id=eqp_key,
            interlock_kind="SPC",
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: m_interlock_selectors.fetch_interlock_timeline_page(
            **options,
            interlock_kind="SPC",
        ),
        serialize_page_row=lambda row: serialize_compact_interlock_row(
            row,
            interlock_kind="SPC",
        ),
        cursor_time_field="event_time",
        fetch_detail=lambda eqp_id, source_id: m_interlock_selectors.get_interlock_timeline_detail(
            eqp_id=eqp_id,
            interlock_kind="SPC",
            source_id=source_id,
        ),
        serialize_detail_row=lambda row: _serialize_log_time_fields(
            _build_interlock_log_item(row, log_type="SPC_ITL")
        ),
    ),
    "fdc-interlock": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_interlock_logs(
            eqp_id=eqp_key,
            interlock_kind="FDC",
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: m_interlock_selectors.fetch_interlock_timeline_page(
            **options,
            interlock_kind="FDC",
        ),
        serialize_page_row=lambda row: serialize_compact_interlock_row(
            row,
            interlock_kind="FDC",
        ),
        cursor_time_field="event_time",
        fetch_detail=lambda eqp_id, source_id: m_interlock_selectors.get_interlock_timeline_detail(
            eqp_id=eqp_id,
            interlock_kind="FDC",
            source_id=source_id,
        ),
        serialize_detail_row=lambda row: _serialize_log_time_fields(
            _build_interlock_log_item(row, log_type="FDC_ITL")
        ),
    ),
    "ctttm": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_ctttm_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: ctttm_workorder_selectors.fetch_ctttm_timeline_page(
            **options
        ),
        serialize_page_row=lambda row: serialize_compact_ctttm_row(
            row,
            base_url=getattr(settings, "DRONE_CTTTM_BASE_URL", ""),
        ),
        cursor_time_field="inprg_date",
        fetch_detail=lambda eqp_id, source_id: ctttm_workorder_selectors.get_ctttm_timeline_detail(
            eqp_id=eqp_id,
            source_id=source_id,
        ),
        serialize_detail_row=_serialize_ctttm_log_detail,
    ),
    "racb": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_racb_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: racb_list_selectors.fetch_racb_timeline_page(
            **options
        ),
        serialize_page_row=lambda row: serialize_compact_racb_row(
            row,
            report_base_url=settings.RACB_REPORT_BASE_URL,
        ),
        cursor_time_field="update_date",
        fetch_detail=lambda eqp_id, source_id: racb_list_selectors.get_racb_timeline_detail(
            eqp_id=eqp_id,
            log_id=str(source_id),
        ),
        serialize_detail_row=_serialize_racb_log_detail,
    ),
    "esop": _ObserverLogSource(
        fetch_logs=lambda eqp_key, start_at, end_at, limit: _fetch_esop_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        ),
        fetch_page=lambda **options: drone_selectors.fetch_drone_sop_timeline_page(
            **options
        ),
        serialize_page_row=serialize_compact_esop_row,
        cursor_time_field="created_at",
        fetch_detail=lambda eqp_id, source_id: drone_selectors.get_drone_sop_timeline_detail(
            eqp_id=eqp_id,
            source_id=source_id,
        ),
        serialize_detail_row=_serialize_esop_log_detail,
    ),
}

OBSERVER_LOG_KEYS = tuple(_OBSERVER_LOG_SOURCES)
OBSERVER_LOG_FETCHERS: Dict[str, LogFetcher] = {
    log_key: source.fetch_logs
    for log_key, source in _OBSERVER_LOG_SOURCES.items()
}

__all__ = [
    '_fetch_eqp_logs',
    '_fetch_tip_logs',
    '_build_interlock_log_item',
    '_fetch_interlock_logs',
    '_fetch_ctttm_logs',
    '_fetch_racb_logs',
    '_unique_sequence',
    '_to_http_url',
    '_normalize_defect_image_row',
    '_build_esop_defect_image_urls',
    '_normalize_esop_defect_maps',
    '_build_esop_chamber_filters',
    '_fetch_esop_logs',
    '_numeric_detail_id',
    '_serialize_eqp_log_detail',
    '_serialize_tip_log_detail',
    '_serialize_ctttm_log_detail',
    '_serialize_racb_log_detail',
    '_serialize_esop_log_detail',
    '_OBSERVER_LOG_SOURCES',
    'OBSERVER_LOG_KEYS',
    'OBSERVER_LOG_FETCHERS',
]
