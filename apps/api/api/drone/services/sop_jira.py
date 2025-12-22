"""Jira integration helpers for Drone SOP pipelines."""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from django.conf import settings
from django.db import transaction
from django.template import Context, Engine
from django.db.models import Case, CharField, DateTimeField, F, Value, When
from django.utils import timezone

from .. import selectors
from ..models import DroneSOP
from .utils import (
    _first_defined,
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DroneSopJiraCreateResult:
    """Drone SOP Jira 생성 실행 결과."""

    candidates: int = 0
    created: int = 0
    updated_rows: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class DroneSopInstantInformResult:
    """Drone SOP 단건 즉시인폼(Jira 생성) 결과."""

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
    verify_ssl: bool = True
    user: str = ""

    @classmethod
    def from_settings(cls) -> "DroneJiraConfig":
        base_url = (getattr(settings, "DRONE_JIRA_BASE_URL", "") or os.getenv("DRONE_JIRA_BASE_URL") or "").strip()
        token = (getattr(settings, "DRONE_JIRA_TOKEN", "") or os.getenv("DRONE_JIRA_TOKEN") or "").strip()
        user = (getattr(settings, "DRONE_JIRA_USER", "") or os.getenv("DRONE_JIRA_USER") or "").strip()
        verify_ssl = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_VERIFY_SSL", None),
                os.getenv("DRONE_JIRA_VERIFY_SSL"),
            ),
            True,
        )
        issue_type = (
            getattr(settings, "DRONE_JIRA_ISSUE_TYPE", "") or os.getenv("DRONE_JIRA_ISSUE_TYPE") or "Task"
        ).strip() or "Task"
        use_bulk_api = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_JIRA_USE_BULK_API", None),
                os.getenv("DRONE_JIRA_USE_BULK_API"),
            ),
            True,
        )
        bulk_size = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_BULK_SIZE", None),
                os.getenv("DRONE_JIRA_BULK_SIZE"),
            ),
            20,
        )
        connect_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_CONNECT_TIMEOUT", None),
                os.getenv("DRONE_JIRA_CONNECT_TIMEOUT"),
            ),
            5,
        )
        read_timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_JIRA_READ_TIMEOUT", None),
                os.getenv("DRONE_JIRA_READ_TIMEOUT"),
            ),
            20,
        )
        return cls(
            base_url=base_url,
            token=token,
            issue_type=issue_type,
            use_bulk_api=use_bulk_api,
            bulk_size=max(1, bulk_size),
            connect_timeout=max(1, connect_timeout),
            read_timeout=max(1, read_timeout),
            verify_ssl=verify_ssl,
            user=user,
        )

    @property
    def create_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/2/issue?sendEvent=true"

    @property
    def bulk_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/rest/api/2/issue/bulk?sendEvent=true"


@dataclass(frozen=True)
class DroneCtttmConfig:
    """CTTTM 조회 및 URL 생성 설정."""

    table_name: str = ""
    base_url: str = ""

    @classmethod
    def from_settings(cls) -> "DroneCtttmConfig":
        table_name = (
            getattr(settings, "DRONE_CTTTM_TABLE_NAME", "")
            or os.getenv("DRONE_CTTTM_TABLE_NAME")
            or ""
        ).strip()
        base_url = (
            getattr(settings, "DRONE_CTTTM_BASE_URL", "")
            or os.getenv("DRONE_CTTTM_BASE_URL")
            or ""
        ).strip()
        return cls(table_name=table_name, base_url=base_url)


def _truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _build_jira_summary(row: dict[str, Any]) -> str:
    sdwt = str(row.get("sdwt_prod") or "?").strip() or "?"
    step = str(row.get("main_step") or "??").strip() or "??"
    normalized_step = step[2:].upper() if len(step) >= 3 else step.upper()
    return _truncate(f"{sdwt[:1]} {normalized_step}", 255)


_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
_TEMPLATE_ENGINE = Engine(autoescape=True)
_TEMPLATE_CACHE: dict[str, str] = {}


def _load_template_files() -> dict[str, str]:
    template_files: dict[str, str] = {}
    if not _TEMPLATE_DIR.exists():
        return template_files
    for path in sorted(_TEMPLATE_DIR.glob("*.html")):
        key = path.stem.strip()
        if not key:
            continue
        template_files[key] = path.name
    return template_files


_TEMPLATE_FILES: dict[str, str] = _load_template_files()


def _build_eqp_cb(row: dict[str, Any]) -> str:
    eqp_id = (str(row.get("eqp_id") or "-") or "-").strip()
    chamber_ids = (str(row.get("chamber_ids") or "-") or "-").strip()
    return f"{eqp_id}-{chamber_ids}"


def _normalize_ctttm_urls(value: Any) -> list[dict[str, str]]:
    urls: list[dict[str, str]] = []
    if isinstance(value, str):
        if value.strip():
            urls.append({"url": value.strip(), "label": value.strip()})
        return urls
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            link = item.get("url")
            if not link:
                continue
            label = item.get("eqp_id") or link
            urls.append({"url": str(link), "label": str(label)})
    return urls


def _build_template_context(row: dict[str, Any]) -> dict[str, Any]:
    knoxid = str(row.get("knox_id") or row.get("knoxid") or "").strip()
    user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    comment_raw = str(row.get("comment") or "").split("$@$", 1)[0]
    return {
        "main_step": row.get("main_step"),
        "ppid": row.get("ppid"),
        "eqp_cb": _build_eqp_cb(row),
        "lot_id": row.get("lot_id"),
        "knoxid": knoxid,
        "user_sdwt_prod": user_sdwt_prod,
        "ctttm_urls": _normalize_ctttm_urls(row.get("url")),
        "defect_url": row.get("defect_url"),
        "comment_raw": comment_raw,
    }


def _load_template_source(template_key: str) -> str:
    filename = _TEMPLATE_FILES.get(template_key)
    if not filename:
        raise ValueError(f"Unsupported Jira template key: {template_key!r}")
    if template_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_key]
    path = _TEMPLATE_DIR / filename
    source = path.read_text(encoding="utf-8")
    _TEMPLATE_CACHE[template_key] = source
    return source


def _render_line_template(*, template_key: str, row: dict[str, Any]) -> str:
    source = _load_template_source(template_key)
    context = Context(_build_template_context(row))
    return _TEMPLATE_ENGINE.from_string(source).render(context)


def _build_jira_description_html(*, row: dict[str, Any], template_key: str) -> str:
    return _render_line_template(template_key=template_key, row=row)


def _build_ctttm_url(*, base_url: str, workorder_id: str, line_id: str) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"wono": workorder_id, "lineId": line_id})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _enrich_rows_with_ctttm_urls(*, rows: Sequence[dict[str, Any]], config: DroneCtttmConfig) -> None:
    if not rows:
        return
    if not config.table_name or not config.base_url:
        return

    sop_ids: list[int] = []
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, int) and rid > 0:
            sop_ids.append(rid)
    if not sop_ids:
        return

    try:
        workorders_by_id = selectors.load_drone_sop_ctttm_workorders_map(sop_ids=sop_ids, ctttm_table=config.table_name)
    except Exception:
        logger.exception("Failed to load CTTTM workorders (table=%r)", config.table_name)
        return

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int) or rid <= 0:
            continue
        entries = workorders_by_id.get(rid) or []
        url_entries: list[dict[str, str]] = []
        for entry in entries:
            eqp_id = str(entry.get("eqp_id") or "").strip()
            workorder_id = str(entry.get("workorder_id") or "").strip()
            line_id = str(entry.get("line_id") or "").strip()
            if not eqp_id or not workorder_id or not line_id:
                continue
            url_entries.append(
                {
                    "eqp_id": eqp_id,
                    "url": _build_ctttm_url(base_url=config.base_url, workorder_id=workorder_id, line_id=line_id),
                }
            )
        if url_entries:
            row["url"] = url_entries


def _jira_session(config: DroneJiraConfig) -> requests.Session:
    sess = requests.Session()
    sess.trust_env = False
    sess.proxies = {}
    sess.verify = bool(config.verify_ssl)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Atlassian-Token": "no-check",
    }
    if config.user and config.token:
        sess.auth = (config.user, config.token)
    elif config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    sess.headers.update(headers)

    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=2,
        status_forcelist=[403, 502, 503, 504],
        allowed_methods=frozenset({"POST"}),
    )
    sess.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20))
    return sess


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bulk_create_jira_issues(
    *,
    rows: Sequence[dict[str, Any]],
    config: DroneJiraConfig,
    session: requests.Session,
    project_key_by_id: dict[int, str],
    template_key_by_id: dict[int, str],
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
            template_key = template_key_by_id.get(rid)
            if not template_key:
                continue
            issue_updates.append(
                {
                    "fields": _build_jira_issue_fields(
                        row=row,
                        project_key=project_key,
                        template_key=template_key,
                        config=config,
                    )
                }
            )
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
    template_key_by_id: dict[int, str],
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
        template_key = template_key_by_id.get(rid)
        if not template_key:
            continue
        resp = session.post(
            config.create_url,
            json={
                "fields": _build_jira_issue_fields(
                    row=row,
                    project_key=project_key,
                    template_key=template_key,
                    config=config,
                )
            },
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


def _build_jira_issue_fields(
    *,
    row: dict[str, Any],
    project_key: str,
    template_key: str,
    config: DroneJiraConfig,
) -> dict[str, Any]:
    return {
        "project": {"key": project_key},
        "issuetype": {"name": config.issue_type},
        "summary": _build_jira_summary(row),
        "description": _build_jira_description_html(row=row, template_key=template_key),
        "labels": ["drone", "drone_sop"],
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
        updated = DroneSOP.objects.filter(id__in=list(done_ids)).update(**updates)
    return int(updated or 0)


def _drone_sop_model_to_row(sop: DroneSOP) -> dict[str, Any]:
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
    """DroneSOP 단건에 대해 조건 무시하고 Jira 이슈를 즉시 생성합니다.

    - needtosend/status 조건을 검사하지 않습니다.
    - Jira 생성에 성공하면 send_jira=1로 업데이트하여 배치 파이프라인에서 재생성되지 않게 합니다.

    Side effects:
        - drone_sop 레코드 comment/instant_inform/send_jira/jira_key/inform_step/informed_at 업데이트
        - Jira API 호출
    """

    if sop_id <= 0:
        raise ValueError("sop_id must be a positive integer")

    config = DroneJiraConfig.from_settings()
    if not config.base_url:
        raise ValueError("DRONE_JIRA_BASE_URL 미설정")

    lock_id = _lock_key("drone_sop_jira_create")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopInstantInformResult(skipped=True, skip_reason="already_running")

    try:
        with transaction.atomic():
            sop = DroneSOP.objects.select_for_update().filter(id=sop_id).first()
            if sop is None:
                raise ValueError("DroneSOP not found")

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

        _enrich_rows_with_ctttm_urls(rows=[row_payload], config=DroneCtttmConfig.from_settings())

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

        project_key = selectors.get_affiliation_jira_key_for_line_and_sdwt(
            line_id=normalized_line_id,
            user_sdwt_prod=normalized_sdwt_prod,
        )
        if not project_key:
            raise ValueError(
                f"jira_key missing for line_id={normalized_line_id!r} user_sdwt_prod={normalized_sdwt_prod!r}"
            )

        template_keys_by_line = selectors.list_drone_sop_jira_templates_by_line_ids(line_ids={normalized_line_id})
        template_keys_by_user_sdwt = selectors.list_drone_sop_jira_templates_by_user_sdwt_prods(
            user_sdwt_prod_values={row_payload.get("user_sdwt_prod")},
        )
        template_key = _resolve_template_key_for_row(
            row=row_payload,
            template_keys_by_user_sdwt=template_keys_by_user_sdwt,
            template_keys_by_line=template_keys_by_line,
        )
        if not template_key:
            logger.warning(
                "Missing Jira template mapping for line_id=%s user_sdwt_prod=%s",
                normalized_line_id,
                row_payload.get("user_sdwt_prod"),
            )
            with transaction.atomic():
                DroneSOP.objects.filter(id=sop_id).update(send_jira=-1)
            return DroneSopInstantInformResult(skipped=True, skip_reason="template_missing")

        sess = _jira_session(config)
        resp = sess.post(
            config.create_url,
            json={
                "fields": _build_jira_issue_fields(
                    row=row_payload,
                    project_key=project_key,
                    template_key=template_key,
                    config=config,
                )
            },
            timeout=(config.connect_timeout, config.read_timeout),
        )
        if resp.status_code != 201:
            with transaction.atomic():
                DroneSOP.objects.filter(id=sop_id).update(instant_inform=-1)
            raise RuntimeError(f"Jira create failed ({resp.status_code})")

        data = _safe_json(resp)
        key = data.get("key") if isinstance(data, dict) else None
        jira_key = key.strip() if isinstance(key, str) and key.strip() else None

        now = timezone.now()
        with transaction.atomic():
            sop = DroneSOP.objects.select_for_update().filter(id=sop_id).first()
            if sop is None:
                raise ValueError("DroneSOP not found")

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
        - drone_sop 상태 컬럼(send_jira/inform_step/jira_key/informed_at) 업데이트
    """

    config = DroneJiraConfig.from_settings()
    if not config.base_url:
        raise ValueError("DRONE_JIRA_BASE_URL 미설정")

    lock_id = _lock_key("drone_sop_jira_create")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopJiraCreateResult(skipped=True, skip_reason="already_running")

    try:
        rows = selectors.list_drone_sop_jira_candidates(limit=limit)
        if not rows:
            return DroneSopJiraCreateResult(candidates=0, created=0, updated_rows=0)

        project_key_by_id, missing_ids = _resolve_project_keys_for_rows(rows=rows)
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
                "Missing Jira project key mapping for %s drone_sop rows (line_ids=%s)",
                len(missing_ids),
                ",".join(missing_line_ids[:10]) if missing_line_ids else "-",
            )
            with transaction.atomic():
                DroneSOP.objects.filter(id__in=missing_ids).update(send_jira=-1)

        template_key_by_id, missing_template_ids = _resolve_template_keys_for_rows(rows=rows)
        if missing_template_ids:
            missing_id_set = set(missing_template_ids)
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
                "Missing Jira template mapping for %s drone_sop rows (line_ids=%s)",
                len(missing_template_ids),
                ",".join(missing_line_ids[:10]) if missing_line_ids else "-",
            )
            with transaction.atomic():
                DroneSOP.objects.filter(id__in=missing_template_ids).update(send_jira=-1)

        rows_to_send = [
            row
            for row in rows
            if isinstance(row.get("id"), int)
            and row.get("id") in project_key_by_id
            and row.get("id") in template_key_by_id
        ]
        if not rows_to_send:
            return DroneSopJiraCreateResult(candidates=len(rows), created=0, updated_rows=0)

        _enrich_rows_with_ctttm_urls(rows=rows_to_send, config=DroneCtttmConfig.from_settings())

        sess = _jira_session(config)
        if config.use_bulk_api:
            done_ids, key_by_id = _bulk_create_jira_issues(
                rows=rows_to_send,
                config=config,
                session=sess,
                project_key_by_id=project_key_by_id,
                template_key_by_id=template_key_by_id,
            )
        else:
            done_ids, key_by_id = _single_create_jira_issues(
                rows=rows_to_send,
                config=config,
                session=sess,
                project_key_by_id=project_key_by_id,
                template_key_by_id=template_key_by_id,
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
) -> tuple[dict[int, str], list[int]]:
    """DroneSOP row 목록에 대해 Jira project key를 해석합니다.

    - account_affiliation(user_sdwt_prod == sdwt_prod) 매핑이 존재해야 합니다.
    - project key는 Affiliation.jira_key에서 가져옵니다.
    - 매핑이 없으면 해당 row id를 missing_ids로 반환합니다.
    """

    sdwt_prod_values: set[str] = set()
    for row in rows:
        sdwt_prod = row.get("sdwt_prod")
        if isinstance(sdwt_prod, str) and sdwt_prod.strip():
            sdwt_prod_values.add(sdwt_prod.strip())

    line_ids: set[str] = set()
    for row in rows:
        line_id = row.get("line_id")
        if isinstance(line_id, str) and line_id.strip():
            line_ids.add(line_id.strip())

    jira_keys_by_line_sdwt = selectors.list_affiliation_jira_keys_by_line_and_sdwt(
        line_ids=line_ids,
        user_sdwt_prod_values=sdwt_prod_values,
    )

    project_key_by_id: dict[int, str] = {}
    missing_ids: list[int] = []

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        project_key = _resolve_project_key_for_row(
            row=row,
            jira_keys_by_line_sdwt=jira_keys_by_line_sdwt,
        )
        if not project_key:
            missing_ids.append(rid)
            continue
        project_key_by_id[rid] = project_key

    return project_key_by_id, missing_ids


def _resolve_template_keys_for_rows(
    *,
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[int, str], list[int]]:
    """DroneSOP row 목록에 대해 Jira 템플릿 키를 해석합니다."""

    line_ids: set[str] = set()
    user_sdwt_prod_values: set[str] = set()
    for row in rows:
        line_id = row.get("line_id")
        if isinstance(line_id, str) and line_id.strip():
            line_ids.add(line_id.strip())
        user_sdwt_prod = row.get("user_sdwt_prod")
        if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
            user_sdwt_prod_values.add(user_sdwt_prod.strip())

    template_keys_by_line = selectors.list_drone_sop_jira_templates_by_line_ids(line_ids=line_ids)
    template_keys_by_user_sdwt = selectors.list_drone_sop_jira_templates_by_user_sdwt_prods(
        user_sdwt_prod_values=user_sdwt_prod_values,
    )

    template_key_by_id: dict[int, str] = {}
    missing_ids: list[int] = []

    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        template_key = _resolve_template_key_for_row(
            row=row,
            template_keys_by_user_sdwt=template_keys_by_user_sdwt,
            template_keys_by_line=template_keys_by_line,
        )
        if not template_key:
            missing_ids.append(rid)
            continue
        template_key_by_id[rid] = template_key

    return template_key_by_id, missing_ids


def _resolve_template_key_for_row(
    *,
    row: dict[str, Any],
    template_keys_by_user_sdwt: dict[str, str],
    template_keys_by_line: dict[str, str],
) -> str | None:
    """단일 DroneSOP row에 대한 Jira 템플릿 키를 반환합니다."""

    user_sdwt_prod = row.get("user_sdwt_prod")
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        normalized_user = user_sdwt_prod.strip()
        template_key = template_keys_by_user_sdwt.get(normalized_user)
        if isinstance(template_key, str) and template_key.strip():
            normalized_key = template_key.strip()
            if normalized_key in _TEMPLATE_FILES:
                return normalized_key
            return None

    line_id = row.get("line_id")
    if not isinstance(line_id, str) or not line_id.strip():
        return None

    normalized_line_id = line_id.strip()
    template_key = template_keys_by_line.get(normalized_line_id)
    if not isinstance(template_key, str) or not template_key.strip():
        return None
    normalized_key = template_key.strip()
    if normalized_key not in _TEMPLATE_FILES:
        return None
    return normalized_key


def _resolve_project_key_for_row(
    *,
    row: dict[str, Any],
    jira_keys_by_line_sdwt: dict[tuple[str, str], str | None],
) -> str | None:
    """단일 DroneSOP row에 대한 Jira project key를 반환합니다."""

    line_id = row.get("line_id")
    sdwt_prod = row.get("sdwt_prod")
    if not isinstance(line_id, str) or not line_id.strip():
        return None
    if not isinstance(sdwt_prod, str) or not sdwt_prod.strip():
        return None

    normalized_line_id = line_id.strip()
    normalized_sdwt_prod = sdwt_prod.strip()
    project_key = jira_keys_by_line_sdwt.get((normalized_line_id, normalized_sdwt_prod))
    if not isinstance(project_key, str) or not project_key.strip():
        return None
    return project_key.strip()
