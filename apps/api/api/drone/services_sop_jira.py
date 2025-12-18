"""Jira integration helpers for Drone SOP v3 pipelines."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Sequence

import requests

from django.conf import settings
from django.db import transaction
from django.db.models import Case, CharField, DateTimeField, F, Value, When
from django.utils import timezone

from . import selectors
from .models import DroneSOPV3
from .services_utils import (
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DroneSopJiraCreateResult:
    """Drone SOP v3 Jira 생성 실행 결과."""

    candidates: int = 0
    created: int = 0
    updated_rows: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class DroneSopInstantInformResult:
    """Drone SOP v3 단건 즉시인폼(Jira 생성) 결과."""

    created: bool = False
    already_informed: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    jira_key: str | None = None
    updated_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DroneJiraConfig:
    """Jira 연동 설정."""

    base_url: str
    token: str
    issue_type: str = "Task"
    use_bulk_api: bool = True
    bulk_size: int = 20
    connect_timeout: int = 5
    read_timeout: int = 20
    project_key_by_line: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> "DroneJiraConfig":
        base_url = (getattr(settings, "DRONE_JIRA_BASE_URL", "") or os.getenv("DRONE_JIRA_BASE_URL") or "").strip()
        token = (getattr(settings, "DRONE_JIRA_TOKEN", "") or os.getenv("DRONE_JIRA_TOKEN") or "").strip()
        issue_type = (
            getattr(settings, "DRONE_JIRA_ISSUE_TYPE", "") or os.getenv("DRONE_JIRA_ISSUE_TYPE") or "Task"
        ).strip() or "Task"
        use_bulk_api = _parse_bool(
            getattr(settings, "DRONE_JIRA_USE_BULK_API", None) or os.getenv("DRONE_JIRA_USE_BULK_API"),
            True,
        )
        bulk_size = _parse_int(getattr(settings, "DRONE_JIRA_BULK_SIZE", None) or os.getenv("DRONE_JIRA_BULK_SIZE"), 20)
        connect_timeout = _parse_int(
            getattr(settings, "DRONE_JIRA_CONNECT_TIMEOUT", None) or os.getenv("DRONE_JIRA_CONNECT_TIMEOUT"),
            5,
        )
        read_timeout = _parse_int(
            getattr(settings, "DRONE_JIRA_READ_TIMEOUT", None) or os.getenv("DRONE_JIRA_READ_TIMEOUT"),
            20,
        )
        project_key_by_line_raw = getattr(settings, "DRONE_JIRA_PROJECT_KEY_BY_LINE", None)
        if project_key_by_line_raw is None:
            project_key_by_line_raw = os.getenv("DRONE_JIRA_PROJECT_KEY_BY_LINE") or ""
        project_key_by_line = _parse_project_key_by_line(project_key_by_line_raw)

        return cls(
            base_url=base_url,
            token=token,
            issue_type=issue_type,
            use_bulk_api=use_bulk_api,
            bulk_size=max(1, bulk_size),
            connect_timeout=max(1, connect_timeout),
            read_timeout=max(1, read_timeout),
            project_key_by_line=project_key_by_line,
        )

    @property
    def create_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/2/issue"

    @property
    def bulk_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/2/issue/bulk"


def _truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _build_jira_summary(row: dict[str, Any]) -> str:
    parts = [
        "[drone_sop_v3]",
        str(row.get("line_id") or "-"),
        str(row.get("eqp_id") or "-"),
        str(row.get("chamber_ids") or "-"),
        str(row.get("lot_id") or "-"),
        str(row.get("main_step") or "-"),
        str(row.get("metro_current_step") or "-"),
    ]
    return _truncate(" ".join(parts), 255)


def _build_jira_description(row: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in (
        "line_id",
        "sdwt_prod",
        "sample_type",
        "sample_group",
        "eqp_id",
        "chamber_ids",
        "lot_id",
        "proc_id",
        "ppid",
        "main_step",
        "metro_current_step",
        "metro_steps",
        "metro_end_step",
        "status",
        "knox_id",
        "user_sdwt_prod",
        "custom_end_step",
        "needtosend",
    ):
        value = row.get(key)
        if value is None:
            continue
        lines.append(f"{key}: {value}")

    comment = row.get("comment")
    if isinstance(comment, str) and comment.strip():
        lines.append("")
        lines.append("comment:")
        lines.append(comment.strip())

    defect_url = row.get("defect_url")
    if isinstance(defect_url, str) and defect_url.strip():
        lines.append("")
        lines.append(f"defect_url: {defect_url.strip()}")

    return "\n".join(lines) if lines else "(empty)"


def _jira_session(config: DroneJiraConfig) -> requests.Session:
    sess = requests.Session()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    sess.headers.update(headers)
    return sess


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_project_key_by_line(value: Any) -> dict[str, str]:
    """DRONE_JIRA_PROJECT_KEY_BY_LINE을 dict[str, str]로 파싱합니다.

    Accepts either:
        - JSON object string (env var): {"LINE1":"PROJ", "LINE2":"PROJ2"}
        - dict (Django settings override / tests)
    """

    if value is None:
        return {}

    parsed: Any = value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("DRONE_JIRA_PROJECT_KEY_BY_LINE must be a valid JSON object") from exc

    if not isinstance(parsed, dict):
        raise ValueError("DRONE_JIRA_PROJECT_KEY_BY_LINE must be a JSON object mapping line_id to project_key")

    mapping: dict[str, str] = {}
    for line_id, project_key in parsed.items():
        if not isinstance(line_id, str) or not line_id.strip():
            raise ValueError("DRONE_JIRA_PROJECT_KEY_BY_LINE has an invalid line_id key")
        if not isinstance(project_key, str) or not project_key.strip():
            raise ValueError(f"DRONE_JIRA_PROJECT_KEY_BY_LINE has an invalid project_key for line_id={line_id!r}")
        mapping[line_id.strip()] = project_key.strip()

    return mapping


def _bulk_create_jira_issues(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    session: requests.Session,
    project_key_by_id: dict[int, str],
) -> tuple[list[int], dict[int, str]]:
    done_ids: list[int] = []
    key_by_id: dict[int, str] = {}

    for st in range(0, len(rows), config.bulk_size):
        chunk = list(rows[st : st + config.bulk_size])
        issue_updates: list[dict[str, Any]] = []
        valid_chunk: list[dict[str, Any]] = []
        for row in chunk:
            rid = row.get("id")
            if not isinstance(rid, int):
                continue
            project_key = project_key_by_id.get(rid)
            if not project_key:
                continue
            issue_updates.append({"fields": _build_jira_issue_fields(row=row, project_key=project_key, config=config)})
            valid_chunk.append(row)
        if not issue_updates:
            continue
        resp = session.post(
            config.bulk_url,
            json={"issueUpdates": issue_updates},
            timeout=(config.connect_timeout, config.read_timeout),
        )
        if resp.status_code != 201:
            logger.error("Jira bulk create failed %s: %s", resp.status_code, resp.text[:300])
            continue

        data = _safe_json(resp)
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            continue

        for index, row in enumerate(valid_chunk):
            rid = row.get("id")
            if not isinstance(rid, int):
                continue
            if index >= len(issues):
                continue
            issue = issues[index]
            if not isinstance(issue, dict):
                continue
            key = issue.get("key")
            if isinstance(key, str) and key.strip():
                key_by_id[rid] = key.strip()
                done_ids.append(rid)

    return done_ids, key_by_id


def _single_create_jira_issues(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    session: requests.Session,
    project_key_by_id: dict[int, str],
) -> tuple[list[int], dict[int, str]]:
    done_ids: list[int] = []
    key_by_id: dict[int, str] = {}

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        project_key = project_key_by_id.get(rid)
        if not project_key:
            continue
        resp = session.post(
            config.create_url,
            json={"fields": _build_jira_issue_fields(row=row, project_key=project_key, config=config)},
            timeout=(config.connect_timeout, config.read_timeout),
        )
        if resp.status_code != 201:
            logger.error("Jira create failed id=%s %s: %s", rid, resp.status_code, resp.text[:300])
            continue
        data = _safe_json(resp)
        key = data.get("key")
        if isinstance(key, str) and key.strip():
            key_by_id[rid] = key.strip()
        done_ids.append(rid)

    return done_ids, key_by_id


def _build_jira_issue_fields(*, row: dict[str, Any], project_key: str, config: DroneJiraConfig) -> dict[str, Any]:
    return {
        "project": {"key": project_key},
        "issuetype": {"name": config.issue_type},
        "summary": _build_jira_summary(row),
        "description": _build_jira_description(row),
        "labels": ["drone", "drone_sop_v3"],
    }


def _update_drone_sop_jira_status(
    *,
    done_ids: Sequence[int],
    rows: Sequence[dict[str, Any]],
    key_by_id: dict[int, str],
) -> int:
    if not done_ids:
        return 0

    step_by_id: dict[int, str] = {}
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int) or rid not in done_ids:
            continue
        step = row.get("metro_current_step")
        if isinstance(step, str) and step.strip():
            step_by_id[rid] = step.strip()

    now = timezone.now()
    step_whens = [When(id=rid, then=Value(step)) for rid, step in sorted(step_by_id.items())]
    key_whens = [When(id=rid, then=Value(key)) for rid, key in sorted(key_by_id.items())]

    updates: dict[str, Any] = {
        "send_jira": 1,
        "informed_at": Case(
            When(informed_at__isnull=True, then=Value(now)),
            default=F("informed_at"),
            output_field=DateTimeField(),
        ),
    }
    if step_whens:
        updates["inform_step"] = Case(*step_whens, default=F("inform_step"), output_field=CharField())
    if key_whens:
        updates["jira_key"] = Case(*key_whens, default=F("jira_key"), output_field=CharField())

    with transaction.atomic():
        updated = DroneSOPV3.objects.filter(id__in=list(done_ids)).update(**updates)
    return int(updated or 0)


def _drone_sop_model_to_row(sop: DroneSOPV3) -> dict[str, Any]:
    return {
        "id": int(sop.id),
        "line_id": sop.line_id,
        "sdwt_prod": sop.sdwt_prod,
        "sample_type": sop.sample_type,
        "sample_group": sop.sample_group,
        "eqp_id": sop.eqp_id,
        "chamber_ids": sop.chamber_ids,
        "lot_id": sop.lot_id,
        "proc_id": sop.proc_id,
        "ppid": sop.ppid,
        "main_step": sop.main_step,
        "metro_current_step": sop.metro_current_step,
        "metro_steps": sop.metro_steps,
        "metro_end_step": sop.metro_end_step,
        "status": sop.status,
        "knox_id": sop.knox_id,
        "user_sdwt_prod": sop.user_sdwt_prod,
        "comment": sop.comment,
        "defect_url": sop.defect_url,
        "needtosend": sop.needtosend,
        "custom_end_step": sop.custom_end_step,
    }


def run_drone_sop_jira_instant_inform(
    *,
    sop_id: int,
    comment: str | None = None,
) -> DroneSopInstantInformResult:
    """DroneSOPV3 단건에 대해 조건 무시하고 Jira 이슈를 즉시 생성합니다.

    - needtosend/status 조건을 검사하지 않습니다.
    - Jira 생성에 성공하면 send_jira=1로 업데이트하여 배치 파이프라인에서 재생성되지 않게 합니다.

    Side effects:
        - drone_sop_v3 레코드 comment/instant_inform/send_jira/jira_key/inform_step/informed_at 업데이트
        - Jira API 호출
    """

    if sop_id <= 0:
        raise ValueError("sop_id must be a positive integer")

    config = DroneJiraConfig.from_settings()
    if not config.base_url:
        raise ValueError("DRONE_JIRA_BASE_URL 미설정")
    if not config.project_key_by_line:
        raise ValueError("DRONE_JIRA_PROJECT_KEY_BY_LINE 미설정")

    lock_id = _lock_key("drone_sop_jira_create")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopInstantInformResult(skipped=True, skip_reason="already_running")

    try:
        with transaction.atomic():
            sop = DroneSOPV3.objects.select_for_update().filter(id=sop_id).first()
            if sop is None:
                raise ValueError("DroneSOPV3 not found")

            if comment is not None:
                sop.comment = comment
                sop.save(update_fields=["comment", "updated_at"])

            send_jira_value = int(sop.send_jira or 0)
            if send_jira_value > 0:
                updated_fields: dict[str, Any] = {}
                if comment is not None:
                    updated_fields["comment"] = sop.comment
                if sop.jira_key:
                    updated_fields["jira_key"] = sop.jira_key
                updated_fields["send_jira"] = sop.send_jira
                updated_fields["instant_inform"] = sop.instant_inform
                updated_fields["inform_step"] = sop.inform_step
                updated_fields["informed_at"] = sop.informed_at.isoformat() if sop.informed_at else None
                return DroneSopInstantInformResult(
                    already_informed=True,
                    jira_key=sop.jira_key,
                    updated_fields=updated_fields,
                )

            row_payload = _drone_sop_model_to_row(sop)

        line_id = row_payload.get("line_id")
        if not isinstance(line_id, str) or not line_id.strip():
            raise ValueError("line_id is required to resolve Jira project key")
        normalized_line_id = line_id.strip()

        sdwt_prod = row_payload.get("sdwt_prod")
        if not isinstance(sdwt_prod, str) or not sdwt_prod.strip():
            raise ValueError("sdwt_prod is required to resolve Jira project key")
        normalized_sdwt_prod = sdwt_prod.strip()

        valid_lines = set(selectors.list_line_ids_for_user_sdwt_prod(user_sdwt_prod=normalized_sdwt_prod))
        if normalized_line_id not in valid_lines:
            raise ValueError(
                f"account_affiliation mapping missing for sdwt_prod={normalized_sdwt_prod!r} line_id={normalized_line_id!r}"
            )

        project_key = config.project_key_by_line.get(normalized_line_id)
        if not isinstance(project_key, str) or not project_key.strip():
            raise ValueError(f"DRONE_JIRA_PROJECT_KEY_BY_LINE missing for line_id={normalized_line_id!r}")
        project_key = project_key.strip()

        sess = _jira_session(config)
        resp = sess.post(
            config.create_url,
            json={"fields": _build_jira_issue_fields(row=row_payload, project_key=project_key, config=config)},
            timeout=(config.connect_timeout, config.read_timeout),
        )
        if resp.status_code != 201:
            with transaction.atomic():
                DroneSOPV3.objects.filter(id=sop_id).update(instant_inform=-1)
            raise RuntimeError(f"Jira create failed ({resp.status_code})")

        data = _safe_json(resp)
        key = data.get("key") if isinstance(data, dict) else None
        jira_key = key.strip() if isinstance(key, str) and key.strip() else None

        now = timezone.now()
        with transaction.atomic():
            sop = DroneSOPV3.objects.select_for_update().filter(id=sop_id).first()
            if sop is None:
                raise ValueError("DroneSOPV3 not found")

            send_jira_value = int(sop.send_jira or 0)
            if send_jira_value > 0:
                updated_fields: dict[str, Any] = {
                    "send_jira": sop.send_jira,
                    "instant_inform": sop.instant_inform,
                    "jira_key": sop.jira_key,
                    "inform_step": sop.inform_step,
                    "informed_at": sop.informed_at.isoformat() if sop.informed_at else None,
                }
                if comment is not None:
                    updated_fields["comment"] = sop.comment
                return DroneSopInstantInformResult(
                    already_informed=True,
                    jira_key=sop.jira_key,
                    updated_fields=updated_fields,
                )

            sop.send_jira = 1
            sop.instant_inform = 1
            if jira_key:
                sop.jira_key = jira_key
            if sop.metro_current_step:
                sop.inform_step = sop.metro_current_step
            if sop.informed_at is None:
                sop.informed_at = now
            sop.save(
                update_fields=[
                    "send_jira",
                    "instant_inform",
                    "jira_key",
                    "inform_step",
                    "informed_at",
                    "updated_at",
                ]
            )

        updated_fields: dict[str, Any] = {
            "send_jira": 1,
            "instant_inform": 1,
            "jira_key": jira_key,
            "inform_step": row_payload.get("metro_current_step"),
            "informed_at": now.isoformat(),
        }
        if comment is not None:
            updated_fields["comment"] = comment

        return DroneSopInstantInformResult(
            created=True,
            jira_key=jira_key,
            updated_fields=updated_fields,
        )
    finally:
        if acquired:
            _release_advisory_lock(lock_id)


def run_drone_sop_jira_create_from_env(*, limit: int | None = None) -> DroneSopJiraCreateResult:
    """send_jira=0 & needtosend=1 & status=COMPLETE 대상 Jira 이슈를 생성합니다.

    Side effects:
        - Jira API 호출
        - drone_sop_v3 상태 컬럼(send_jira/inform_step/jira_key/informed_at) 업데이트
    """

    config = DroneJiraConfig.from_settings()
    if not config.base_url:
        raise ValueError("DRONE_JIRA_BASE_URL 미설정")
    if not config.project_key_by_line:
        raise ValueError("DRONE_JIRA_PROJECT_KEY_BY_LINE 미설정")

    lock_id = _lock_key("drone_sop_jira_create")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopJiraCreateResult(skipped=True, skip_reason="already_running")

    try:
        rows = selectors.list_drone_sop_jira_candidates(limit=limit)
        if not rows:
            return DroneSopJiraCreateResult(candidates=0, created=0, updated_rows=0)

        project_key_by_id, missing_ids = _resolve_project_keys_for_rows(rows=rows, config=config)
        if missing_ids:
            missing_id_set = set(missing_ids)
            missing_line_ids = sorted(
                {
                    row.get("line_id", "").strip()
                    for row in rows
                    if row.get("id") in missing_id_set
                    and isinstance(row.get("line_id"), str)
                    and row.get("line_id").strip()
                }
            )
            logger.warning(
                "Missing Jira project key mapping for %s drone_sop_v3 rows (line_ids=%s)",
                len(missing_ids),
                ",".join(missing_line_ids[:10]) if missing_line_ids else "-",
            )
            with transaction.atomic():
                DroneSOPV3.objects.filter(id__in=missing_ids).update(send_jira=-1)

        rows_to_send = [row for row in rows if isinstance(row.get("id"), int) and row.get("id") in project_key_by_id]
        if not rows_to_send:
            return DroneSopJiraCreateResult(candidates=len(rows), created=0, updated_rows=0)

        sess = _jira_session(config)
        if config.use_bulk_api:
            done_ids, key_by_id = _bulk_create_jira_issues(
                rows=rows_to_send,
                config=config,
                session=sess,
                project_key_by_id=project_key_by_id,
            )
        else:
            done_ids, key_by_id = _single_create_jira_issues(
                rows=rows_to_send,
                config=config,
                session=sess,
                project_key_by_id=project_key_by_id,
            )

        updated = _update_drone_sop_jira_status(done_ids=done_ids, rows=rows_to_send, key_by_id=key_by_id)
        return DroneSopJiraCreateResult(
            candidates=len(rows),
            created=len(done_ids),
            updated_rows=updated,
        )
    finally:
        if acquired:
            _release_advisory_lock(lock_id)


def _resolve_project_keys_for_rows(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
) -> tuple[dict[int, str], list[int]]:
    """DroneSOPV3 row 목록에 대해 Jira project key를 해석합니다.

    - account_affiliation(user_sdwt_prod == sdwt_prod) 매핑이 존재하고,
      row.line_id가 해당 user_sdwt_prod의 라인 목록에 포함되어야 합니다.
    - project key는 DRONE_JIRA_PROJECT_KEY_BY_LINE[line_id]에서 가져옵니다.
    - 매핑이 없으면 해당 row id를 missing_ids로 반환합니다.
    """

    sdwt_prod_values: set[str] = set()
    for row in rows:
        sdwt_prod = row.get("sdwt_prod")
        if isinstance(sdwt_prod, str) and sdwt_prod.strip():
            sdwt_prod_values.add(sdwt_prod.strip())

    lines_by_sdwt_prod: dict[str, set[str]] = {}
    for sdwt_prod in sorted(sdwt_prod_values):
        lines = selectors.list_line_ids_for_user_sdwt_prod(user_sdwt_prod=sdwt_prod)
        lines_by_sdwt_prod[sdwt_prod] = {line.strip() for line in lines if isinstance(line, str) and line.strip()}

    project_key_by_id: dict[int, str] = {}
    missing_ids: list[int] = []

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        project_key = _resolve_project_key_for_row(row=row, config=config, lines_by_sdwt_prod=lines_by_sdwt_prod)
        if not project_key:
            missing_ids.append(rid)
            continue
        project_key_by_id[rid] = project_key

    return project_key_by_id, missing_ids


def _resolve_project_key_for_row(
    *,
    row: dict[str, Any],
    config: DroneJiraConfig,
    lines_by_sdwt_prod: dict[str, set[str]] | None = None,
) -> str | None:
    """단일 DroneSOPV3 row에 대한 Jira project key를 반환합니다."""

    line_id = row.get("line_id")
    sdwt_prod = row.get("sdwt_prod")
    if not isinstance(line_id, str) or not line_id.strip():
        return None
    if not isinstance(sdwt_prod, str) or not sdwt_prod.strip():
        return None

    normalized_line_id = line_id.strip()
    normalized_sdwt_prod = sdwt_prod.strip()
    valid_lines = None
    if lines_by_sdwt_prod is not None:
        valid_lines = lines_by_sdwt_prod.get(normalized_sdwt_prod)
    if valid_lines is None:
        valid_lines = set(selectors.list_line_ids_for_user_sdwt_prod(user_sdwt_prod=normalized_sdwt_prod))
    if normalized_line_id not in valid_lines:
        return None

    project_key = config.project_key_by_line.get(normalized_line_id)
    if not isinstance(project_key, str) or not project_key.strip():
        return None
    return project_key.strip()
