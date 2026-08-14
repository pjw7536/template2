"""L3 Spider 파일 metadata와 제외 규칙 조회를 처리합니다."""

from __future__ import annotations

import fnmatch
import functools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from api.l3_spider import selectors

from . import line_name_rules
from .analytics import _normalize_display_status
from .state import (
    L3SpiderServiceError,
    MAIL_EVENT_COLUMNS,
    SUMMARY_COLUMNS,
    _COMPLETED_DATES_KEY,
    _DAILY_SUMMARY_COLUMNS,
    _DAILY_SUMMARY_COLUMNS_SLIM,
    _LINE_RULE_CANDIDATES_KEY,
    _MAX_PARALLEL_WORKERS,
    _MetaCombo,
    _STATS_COLUMNS,
    _SUMMARY_COLUMNS_SLIM,
    _SUMMARY_DEDUP_KEYS,
    _completed_dates_cache,
    _line_groups_cache,
    _line_rule_candidates_cache,
    _meta_cache,
    _meta_combos_cache,
)

def _parse_filename_key(path: Path) -> tuple[str, str] | None:
    """파일명에서 (step_seq, ppid)를 파싱합니다."""
    try:
        name = path.name
        if name.endswith(".parquet"):
            name = name[: -len(".parquet")]
        parts = name.split("#")
        if len(parts) == 3 and parts[0] and parts[1]:
            return parts[0], parts[1]
    except Exception:
        pass
    return None


def _add_path_context(frame: pd.DataFrame, path: Path, *, override_filename_keys: bool = False) -> pd.DataFrame:
    relative_parts = path.relative_to(selectors.get_data_root()).parts
    # parts: (date, line_id, process_id, eds_step, filename)
    if len(relative_parts) >= 1:
        frame["date"] = relative_parts[0]
    if len(relative_parts) >= 2:
        frame["line_id"] = relative_parts[1]
    if len(relative_parts) >= 3:
        frame["process_id"] = relative_parts[2]
    if len(relative_parts) >= 4:
        frame["eds_step"] = relative_parts[3]

    parsed = _parse_filename_key(path)
    if not parsed:
        return frame

    step_seq, ppid = parsed
    if override_filename_keys or "step_seq" not in frame.columns:
        frame["step_seq"] = step_seq
    else:
        frame["step_seq"] = frame["step_seq"].fillna(step_seq)
    if override_filename_keys or "ppid" not in frame.columns:
        frame["ppid"] = ppid
    else:
        frame["ppid"] = frame["ppid"].fillna(ppid)
    return frame


# ─── 병렬 파일 읽기 ──────────────────────────────────────────────────────────

def _read_summary_file(path: Path) -> pd.DataFrame | None:
    """summary 읽기 단일 파일 처리 (ThreadPoolExecutor용)."""
    try:
        parsed = _parse_filename_key(path)
        cols = _SUMMARY_COLUMNS_SLIM if parsed else SUMMARY_COLUMNS
        frame = selectors.read_parquet_columns(path, cols)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        available_dedup = [c for c in _SUMMARY_DEDUP_KEYS if c in frame.columns]
        return frame.drop_duplicates(subset=available_dedup) if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider summary read failed: {path}: {exc}")
        return None


def _read_daily_summary_file(path: Path) -> pd.DataFrame | None:
    """daily summary 읽기: 카운트 집계용으로 dedup 없이 전체 행을 반환합니다."""
    try:
        parsed = _parse_filename_key(path)
        cols = _DAILY_SUMMARY_COLUMNS_SLIM if parsed else _DAILY_SUMMARY_COLUMNS
        frame = selectors.read_parquet_columns(path, cols)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider daily summary read failed: {path}: {exc}")
        return None


def _read_stats_file(path: Path) -> pd.DataFrame | None:
    """stats 읽기: 3컬럼만 읽고 파일명에서 eds_step/step_seq/ppid 추가."""
    try:
        parsed = _parse_filename_key(path)
        frame = selectors.read_parquet_columns(path, _STATS_COLUMNS)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path, override_filename_keys=bool(parsed))
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider stats read failed: {path}: {exc}")
        return None


def _read_mail_event_file(path: Path) -> pd.DataFrame | None:
    """메일 알림 후보 이벤트를 읽기 위한 단일 파일 처리."""

    try:
        frame = selectors.read_parquet_columns(path, MAIL_EVENT_COLUMNS)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path)
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider mail event read failed: {path}: {exc}")
        return None


def _read_chart_file(path: Path, columns: list[str]) -> pd.DataFrame | None:
    """차트 읽기 단일 파일 처리 (ThreadPoolExecutor용)."""
    try:
        frame = selectors.read_parquet_columns(path, columns)
        frame = _normalize_display_status(frame)
        frame = _add_path_context(frame, path)
        return frame if not frame.empty else None
    except Exception as exc:
        print(f"[WARN] L3 Spider parquet read failed: {path}: {exc}")
        return None


def _parallel_read(files: list[Path], reader_fn) -> list[pd.DataFrame]:
    """파일 목록을 ThreadPoolExecutor로 병렬 읽습니다."""
    if not files:
        return []
    if len(files) == 1:
        result = reader_fn(files[0])
        return [result] if result is not None else []
    max_workers = min(_MAX_PARALLEL_WORKERS, len(files))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(reader_fn, f) for f in files]
        results = [fut.result() for fut in futures]
    return [df for df in results if df is not None]


def _read_frames(selection: dict[str, object], columns: list[str]) -> list[pd.DataFrame]:
    """선택된 파일들을 DataFrame 목록으로 읽습니다 (병렬)."""
    try:
        files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc
    return _parallel_read(files, functools.partial(_read_chart_file, columns=columns))


def _read_summary_frames(selection: dict[str, object]) -> list[pd.DataFrame]:
    """summary 전용 최적화 읽기 (병렬)."""
    try:
        files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc
    return _parallel_read(files, _read_summary_file)


# ─── 서비스 함수 ─────────────────────────────────────────────────────────────

def _get_completed_dates() -> set[str] | None:
    """완료 날짜를 공유 TTL 캐시에서 반환합니다."""

    cached = _completed_dates_cache.get(_COMPLETED_DATES_KEY)
    if cached is not None:
        return cached

    completed_dates = selectors.query_completed_dates()
    if completed_dates is not None:
        _completed_dates_cache.set(_COMPLETED_DATES_KEY, completed_dates)
    return completed_dates


def _get_meta_combos(selected_date: str) -> list[_MetaCombo]:
    """선택 날짜의 실행 통계 조합을 날짜별 TTL 캐시에서 반환합니다."""

    cached = _meta_combos_cache.get(selected_date)
    if cached is not None:
        return cached

    combos = selectors.query_date_line_process_eds_step(selected_date)
    _meta_combos_cache.set(selected_date, combos)
    return combos


def _get_raw_file_rows(combos: list[_MetaCombo]) -> list[dict[str, str]]:
    """선택 날짜의 실행 통계 조합에서 Meta 기본 선택 항목을 반환합니다.

    빈 목록도 유효한 결과로 취급해 동일 요청 안에서 PostgreSQL을 다시 조회하지 않습니다.
    """
    return [
        {
            "date": date,
            "line_id": line_id,
            "process_id": process_id,
            "eds_step": eds_step,
        }
        for date, line_id, process_id, eds_step, _step_seq
        in combos
    ]


def _build_line_groups(selected_date: str, combos: list[_MetaCombo]) -> list[dict]:
    """[{lineName, lineId, processIds}] — 선택 날짜의 line_name 매핑(TTL 캐시).

    Chart 드릴/조회에서 line_name→line_id 해석용. 행 단위 line_name 필터가 정확성을 보장하므로
    제외 필터와 무관한 날짜별 규칙 독립 캐시를 사용합니다. 규칙 미매칭 조합은 line_id로 폴백합니다.
    """
    cached = _line_groups_cache.get(selected_date)
    if cached is not None:
        return cached
    try:
        groups = _build_line_groups_impl(combos)
    except Exception:
        groups = []
    _line_groups_cache.set(selected_date, groups)
    return groups


def _build_line_name_availability(rules: list, combos: list[_MetaCombo]) -> dict:
    """{date: {lineName: {processId: [edsStep]}}} — '그 날짜에 실제로 존재하는' line_name→process→eds.

    line_name은 step_seq로 갈리므로(override), 어떤 날 그 line_name이 어떤 process·eds를 갖는지는
    날짜마다 다를 수 있다. 패널이 '그 날 없는 조합'을 선택지로 내놓아 하위가 비는 문제를 없애기
    위해 날짜별로 내려준다. 제외 필터(rules)의 경로 필드(line_id/process/eds/step_seq)를 적용해,
    제외된 조합이 패널에 남지 않게 한다(eqc·bin 기준 규칙은 컬럼이 없어 자동 무시).
    """
    if not combos:
        return {}
    df = pd.DataFrame(
        combos,
        columns=["date", "line_id", "process_id", "eds_step", "step_seq"],
    )
    df = _apply_exclusion_filters_with_rules(df, rules)
    if df.empty:
        return {}
    lna: dict[str, dict[str, dict[str, set[str]]]] = {}   # date -> lineName -> process -> {eds}
    for row in df.itertuples(index=False):
        name = line_name_rules.resolve_line_name(row.line_id, row.process_id, row.step_seq)
        lna.setdefault(str(row.date), {}).setdefault(name, {}) \
           .setdefault(str(row.process_id), set()).add(str(row.eds_step))
    return {
        date: {
            name: {p: sorted(es) for p, es in sorted(procs.items())}
            for name, procs in sorted(names.items())
        }
        for date, names in sorted(lna.items())
    }


def _filter_files_by_line_names(files: list, selection: dict[str, object]) -> list:
    """선택된 line_name(들)이 있으면 파일 목록을 line_name 기준으로 필터합니다.

    각 파일의 line_name = resolve(line_id, process_id, step_seq) — 전부 경로/파일명에서 얻으므로
    parquet를 읽지 않습니다.

    계약: daily_anomaly 파일명은 항상 {step_seq}#{ppid}#{index} 형식이라 step_seq가 파일명에
    반드시 존재합니다(알고리즘 서버 보장). 따라서 파일 단위로 line_name이 하나로 정해집니다.
    파일명에서 step_seq를 못 읽으면 계약 위반이므로, 조용히 유실하지 않고 경고 후 제외합니다.
    """
    line_names = {str(v) for v in (selection.get("lineNames") or []) if v}
    if not line_names:
        return list(files)
    root = selectors.get_data_root()
    filtered: list = []
    for path in files:
        parsed = _parse_filename_key(path)
        if not parsed:
            print(f"[WARN] L3 Spider lineNames 필터: step_seq 없는 파일명(계약 위반) 제외: {path}")
            continue
        step_seq, _ppid = parsed
        parts = path.relative_to(root).parts
        if len(parts) < 4:
            continue
        line_id, process_id = parts[1], parts[2]
        if line_name_rules.resolve_line_name(line_id, process_id, step_seq) in line_names:
            filtered.append(path)
    return filtered


def _build_line_groups_impl(combos: list[_MetaCombo]) -> list[dict]:
    # 규칙 기반: 선택 날짜의 (line_id, process_id, step_seq) 조합을 resolve_line_name으로
    # line_name에 매핑한다. step_seq마다 line_name이 달라질 수 있어
    # (override) 한 (line_id, process)가 여러 line_name에 나타날 수 있다. line_name→line_id 해석용.
    groups: dict[str, dict[str, dict[str, set[str]]]] = {}   # lineName -> lineId -> process -> {eds}
    for _date, line_id, process_id, eds_step, step_seq in combos:
        line_name = line_name_rules.resolve_line_name(line_id, process_id, step_seq)
        groups.setdefault(line_name, {}).setdefault(str(line_id), {}).setdefault(str(process_id), set()).add(
            str(eds_step),
        )
    result = [
        {
            "lineName": ln,
            "lineId": lid,
            "processIds": sorted(proc_eds),
            "procEds": {pid: sorted(eds_steps) for pid, eds_steps in sorted(proc_eds.items())},
        }
        for ln in sorted(groups)
        for lid, proc_eds in sorted(groups[ln].items())
    ]
    # CSV에 정의된 라인은 file_index 데이터 없어도 meta에 포함 (이상감지 없는 라인도 표시)
    existing = {g["lineName"] for g in result}
    for ln in line_name_rules.get_configured_line_names():
        if ln not in existing:
            result.append({"lineName": ln, "lineId": "", "processIds": [], "procEds": {}})
    return result


def get_unmapped_line_name_rules() -> dict[str, object]:
    """CSV 규칙에 매칭되지 않은 실제 분석 조합을 반환합니다."""

    candidates = _line_rule_candidates_cache.get(_LINE_RULE_CANDIDATES_KEY)
    if candidates is None:
        candidates = selectors.query_line_rule_candidates()
        _line_rule_candidates_cache.set(_LINE_RULE_CANDIDATES_KEY, candidates)

    items = []
    for row in candidates:
        _line_name, is_mapped = line_name_rules.resolve_line_name_mapping(
            row["line_id"],
            row["process_id"],
            row["step_seq"],
        )
        if is_mapped:
            continue
        items.append({
            "lineId": row["line_id"],
            "processId": row["process_id"],
            "stepSeq": row["step_seq"],
            "firstSeenDate": row["first_seen_date"],
            "lastSeenDate": row["last_seen_date"],
            "dateCount": row["date_count"],
        })

    return {
        "count": len(items),
        "items": items,
        "rulesFile": "public.l3_spider_line_name_rule",
    }


def _empty_meta_result(dates: list[str]) -> dict[str, object]:
    """완료 날짜만 포함한 빈 Meta 응답을 반환합니다."""

    return {
        "dates": dates,
        "lineIds": [],
        "processIds": [],
        "edsSteps": [],
        "availability": {},
        "lineGroups": [],
        "lineNameAvailability": {},
    }


def get_meta(*, selected_date: str | None = None, user: Any | None = None) -> dict[str, object]:
    """사용 가능한 날짜/라인/프로세스/EDS step 메타데이터를 반환합니다.

    활성 제외 필터의 경로 필드(line_id, process_id, eds_step)를 적용하여
    완전히 제외된 항목은 DataSelector에 표시되지 않습니다.
    """
    if selected_date is None:
        cached_dates_result = _meta_cache.get("dates")
        if cached_dates_result is not None:
            return cached_dates_result

        completed_dates = _get_completed_dates()
        result = _empty_meta_result(sorted(completed_dates or set()))
        _meta_cache.set("dates", result)
        return result

    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{selected_date}:{rules_hash}"
    cached = _meta_cache.get(cache_key)
    if cached is not None:
        return cached

    completed_dates = _get_completed_dates()
    dates = sorted(completed_dates) if completed_dates is not None else [selected_date]
    if completed_dates is not None and selected_date not in completed_dates:
        result = _empty_meta_result(dates)
        _meta_cache.set(cache_key, result)
        return result

    # 세 Meta 결과가 선택 날짜의 같은 PostgreSQL 조회 결과를 사용합니다.
    combos = _get_meta_combos(selected_date)
    file_rows = _get_raw_file_rows(combos)

    if file_rows:
        df = pd.DataFrame(file_rows).drop_duplicates()
        # step_seq·ppid·eqc·bin_name 컬럼 없음 → 해당 필드 규칙은 자동으로 무시
        df = _apply_exclusion_filters_with_rules(df, rules)
    else:
        df = pd.DataFrame(columns=["date", "line_id", "process_id", "eds_step"])

    line_ids: set[str] = set()
    process_ids: set[str] = set()
    eds_steps: set[str] = set()
    availability: dict[str, dict[str, dict[str, set[str]]]] = {}

    for row in df.itertuples(index=False):
        line_ids.add(row.line_id)
        process_ids.add(row.process_id)
        eds_steps.add(row.eds_step)
        availability.setdefault(row.date, {}).setdefault(row.line_id, {}).setdefault(row.process_id, set()).add(row.eds_step)

    result = {
        "dates": dates,
        "lineIds": sorted(line_ids),
        "processIds": sorted(process_ids),
        "edsSteps": sorted(eds_steps),
        "availability": {
            date: {
                line_id: {
                    process_id: sorted(process_eds_steps)
                    for process_id, process_eds_steps in sorted(processes.items())
                }
                for line_id, processes in sorted(lines.items())
            }
            for date, lines in sorted(availability.items())
        },
        "lineGroups": _build_line_groups(selected_date, combos),
        "lineNameAvailability": _build_line_name_availability(rules, combos),
    }
    _meta_cache.set(cache_key, result)
    return result


def _matches_pattern(value: str, pattern: str) -> bool:
    """와일드카드 패턴 매칭 (* 또는 % 를 임의 문자열로, 대소문자 무시)."""
    if pattern == "*":
        return True
    return fnmatch.fnmatch(str(value).lower(), pattern.replace("%", "*").lower())


def _matches_comma_separated_patterns(value: str, pattern: str) -> bool:
    """쉼표로 구분한 패턴 중 하나라도 값과 일치하는지 반환합니다."""

    patterns = [token.strip() for token in str(pattern).split(",") if token.strip()]
    return any(_matches_pattern(value, token) for token in patterns)


def _get_exclusion_rules(*, user: Any | None = None) -> list[dict]:
    """사용자 소유 활성 제외 필터 규칙을 DB에서 조회합니다.

    multi-worker 환경에서 캐시 불일치를 방지하기 위해 항상 DB를 직접 읽습니다.
    rules 테이블은 소규모이므로 쿼리 비용이 무시할 수준입니다.
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        return []

    try:
        from ..models import L3SpiderExclusionFilter
        return list(
            L3SpiderExclusionFilter.objects.filter(
                is_active=True,
                created_by_id=user_id,
            ).values(
                "line_id", "process_id", "eds_step", "step_seq",
                "ppid", "eqpch", "bin_name", "date_from", "date_to",
            )
        )
    except Exception as exc:
        print(f"[WARN] L3 Spider exclusion rules load failed: {exc}")
        return []

def _apply_exclusion_filters_with_rules(merged: pd.DataFrame, rules: list[dict]) -> pd.DataFrame:
    """주어진 rules를 DataFrame에 적용합니다."""
    if not rules:
        return merged

    _FIELD_COL = [
        ("line_id", "line_id"),
        ("process_id", "process_id"),
        ("eds_step", "eds_step"),
        ("step_seq", "step_seq"),
        ("ppid", "ppid"),
        ("eqpch", "eqc"),
        ("bin_name", "bin_name"),
    ]

    exclude_mask = pd.Series(False, index=merged.index)

    for rule in rules:
        row_mask = pd.Series(True, index=merged.index)

        for field, col in _FIELD_COL:
            pattern = rule.get(field) or "*"
            if pattern == "*":
                continue
            if col not in merged.columns:
                row_mask = pd.Series(False, index=merged.index)
                break
            matcher = (
                _matches_comma_separated_patterns
                if field == "bin_name"
                else _matches_pattern
            )
            row_mask = row_mask & merged[col].astype(str).apply(
                lambda v, p=pattern, match=matcher: match(v, p)
            )

        # 파일 경로 date 폴더명 기준 날짜 범위 (선택 날짜와 동일 기준)
        date_from = rule.get("date_from")
        date_to = rule.get("date_to")
        if (date_from or date_to) and "date" in merged.columns:
            date_col = merged["date"].astype(str)
            if date_from:
                row_mask = row_mask & (date_col >= date_from.isoformat() if hasattr(date_from, "isoformat") else date_col >= str(date_from))
            if date_to:
                row_mask = row_mask & (date_col <= date_to.isoformat() if hasattr(date_to, "isoformat") else date_col <= str(date_to))

        exclude_mask = exclude_mask | row_mask

    return merged[~exclude_mask]


def _apply_exclusion_filters(merged: pd.DataFrame, *, user: Any | None = None) -> pd.DataFrame:
    """활성 제외 필터를 DB에서 읽어 적용합니다 (get_data 전용)."""
    return _apply_exclusion_filters_with_rules(merged, _get_exclusion_rules(user=user))
