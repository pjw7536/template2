"""POP3 ingestion helpers for Drone SOP."""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import poplib
from dataclasses import dataclass
from datetime import timedelta
from email.parser import BytesParser
from email.policy import default
from typing import Any, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .. import selectors
from ..models import DroneSOP, build_sop_key
from .utils import (
    _first_defined,
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)

logger = logging.getLogger(__name__)


def _normalize_blank(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _sanitize_defect_url(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).replace('"', "").strip()
    return cleaned or None


def _extract_first_data_tag(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    data = soup.find("data")
    if not data:
        return {}
    parsed: dict[str, str] = {}
    for child in data.find_all(recursive=False):
        if not child.name:
            continue
        parsed[str(child.name).lower()] = child.get_text(strip=True)
    return parsed


def _strip_prefix_num(value: Optional[str]) -> Optional[int]:
    if not value or len(value) <= 2:
        return None
    numeric = value[2:]
    return int(numeric) if numeric.isdigit() else None


def _as_int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


@dataclass(frozen=True)
class NeedToSendRule:
    """needtosend 계산을 user_sdwt_prod 패턴 기준으로 오버라이드하는 규칙."""

    pattern: str
    comment_last_at: str
    ignore_sample_type: bool = False

    def matches(self, user_sdwt_prod: str) -> bool:
        return fnmatch.fnmatch(user_sdwt_prod, self.pattern)

    def compute(self, row: dict[str, Any]) -> int:
        comment = str(row.get("comment") or "").strip()
        last_at = comment.split("@")[-1] if comment else ""
        if not self.ignore_sample_type:
            sample_type = str(row.get("sample_type") or "").strip()
            if sample_type == "ENGR_PRODUCTION":
                return 0
        return _as_int_bool(last_at == self.comment_last_at)


def _parse_needtosend_rules(value: Any) -> list[NeedToSendRule]:
    """DRONE_SOP_NEEDTOSEND_RULES 설정을 파싱합니다.

    Supports:
        - JSON string: [{"pattern":"aaa*","commentLastAt":"$abc","ignoreSampleType":true}, ...]
        - python list of dicts (tests / settings overrides)
    """

    if value is None:
        return []

    parsed: Any = value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("DRONE_SOP_NEEDTOSEND_RULES must be a valid JSON array") from exc

    if not isinstance(parsed, list):
        raise ValueError("DRONE_SOP_NEEDTOSEND_RULES must be a JSON array of objects")

    rules: list[NeedToSendRule] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        pattern = str(entry.get("pattern") or entry.get("glob") or "").strip()
        comment_last_at = str(
            entry.get("comment_last_at")
            or entry.get("commentLastAt")
            or entry.get("lastAt")
            or entry.get("expected")
            or ""
        ).strip()
        if not pattern or not comment_last_at:
            continue
        ignore_sample_type = bool(entry.get("ignore_sample_type") or entry.get("ignoreSampleType") or False)
        rules.append(
            NeedToSendRule(
                pattern=pattern,
                comment_last_at=comment_last_at,
                ignore_sample_type=ignore_sample_type,
            )
        )
    return rules


def _compute_needtosend_default(row: dict[str, Any]) -> int:
    sample_type = str(row.get("sample_type") or "").strip()
    comment = str(row.get("comment") or "").strip()
    last_at = comment.split("@")[-1] if comment else ""
    return _as_int_bool((sample_type != "ENGR_PRODUCTION") and (last_at == "$SETUP_EQP"))


def _compute_needtosend(*, row: dict[str, Any], rules: Sequence[NeedToSendRule]) -> int:
    user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    if user_sdwt_prod and rules:
        for rule in rules:
            if rule.matches(user_sdwt_prod):
                return rule.compute(row)
    return _compute_needtosend_default(row)


def _extract_html_from_email(msg: Any) -> Optional[str]:
    html = next(
        (part.get_content() for part in msg.walk() if part.get_content_type() == "text/html"),
        None,
    )
    if html:
        return html
    if getattr(msg, "get_content_type", lambda: None)() == "text/html":
        return msg.get_content()
    return None


def _build_drone_sop_row(
    *,
    html: str,
    early_inform_map: dict[tuple[str, str], Optional[str]],
    needtosend_rules: Sequence[NeedToSendRule] | None = None,
) -> Optional[dict[str, Any]]:
    data = _extract_first_data_tag(html)
    if not data:
        return None

    normalized = {key: _normalize_blank(value) for key, value in data.items()}
    knox_value = normalized.get("knox_id") or normalized.get("knoxid")

    row: dict[str, Any] = {
        "line_id": normalized.get("line_id"),
        "sdwt_prod": normalized.get("sdwt_prod"),
        "sample_type": normalized.get("sample_type"),
        "sample_group": normalized.get("sample_group"),
        "eqp_id": normalized.get("eqp_id"),
        "chamber_ids": (str(normalized.get("chamber_ids") or "").replace(",", "")) or None,
        "lot_id": normalized.get("lot_id"),
        "proc_id": normalized.get("proc_id"),
        "ppid": normalized.get("ppid"),
        "main_step": normalized.get("main_step"),
        "metro_current_step": normalized.get("metro_current_step"),
        "metro_steps": normalized.get("metro_steps"),
        "metro_end_step": normalized.get("metro_end_step"),
        "status": normalized.get("status"),
        "knox_id": knox_value,
        "user_sdwt_prod": normalized.get("user_sdwt_prod"),
        "comment": normalized.get("comment"),
        "defect_url": _sanitize_defect_url(normalized.get("defect_url")),
        "instant_inform": 0,
    }
    row["sop_key"] = build_sop_key(
        line_id=row.get("line_id"),
        eqp_id=row.get("eqp_id"),
        chamber_ids=row.get("chamber_ids"),
        lot_id=row.get("lot_id"),
        main_step=row.get("main_step"),
    )

    user_sdwt_prod = str(row.get("user_sdwt_prod") or "").strip()
    main_step = str(row.get("main_step") or "").strip()
    custom_end_step = early_inform_map.get((user_sdwt_prod, main_step))
    if custom_end_step is not None:
        row["custom_end_step"] = custom_end_step
        current_num = _strip_prefix_num(str(row.get("metro_current_step") or "").strip() or None)
        end_num = _strip_prefix_num(str(custom_end_step).strip() or None)
        if current_num is not None and end_num is not None and current_num >= end_num:
            row["status"] = "COMPLETE"

    row["needtosend"] = _compute_needtosend(row=row, rules=needtosend_rules or ())
    return row


@dataclass(frozen=True)
class DroneSopPop3IngestResult:
    """Drone SOP POP3 수집 실행 결과."""

    matched_mails: int = 0
    upserted_rows: int = 0
    deleted_mails: int = 0
    pruned_rows: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class DroneSopPop3Config:
    """Drone SOP POP3 수집 설정."""

    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    timeout: int = 60
    subject_contains: str = "[drone_sop]"
    dummy_mode: bool = False
    dummy_mail_messages_url: str = ""
    needtosend_rules: tuple[NeedToSendRule, ...] = ()

    @classmethod
    def from_settings(cls) -> "DroneSopPop3Config":
        host = (
            getattr(settings, "DRONE_SOP_POP3_HOST", "")
            or getattr(settings, "EMAIL_POP3_HOST", "")
            or ""
        ).strip()
        port = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_SOP_POP3_PORT", None),
                getattr(settings, "EMAIL_POP3_PORT", None),
                995,
            ),
            995,
        )
        username = (
            getattr(settings, "DRONE_SOP_POP3_USERNAME", "")
            or getattr(settings, "EMAIL_POP3_USERNAME", "")
            or ""
        ).strip()
        password = (
            getattr(settings, "DRONE_SOP_POP3_PASSWORD", "")
            or getattr(settings, "EMAIL_POP3_PASSWORD", "")
            or ""
        ).strip()
        use_ssl = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_SOP_POP3_USE_SSL", None),
                getattr(settings, "EMAIL_POP3_USE_SSL", None),
            ),
            True,
        )
        timeout = _parse_int(
            _first_defined(
                getattr(settings, "DRONE_SOP_POP3_TIMEOUT", None),
                getattr(settings, "EMAIL_POP3_TIMEOUT", None),
                60,
            ),
            60,
        )
        dummy_mode = _parse_bool(
            _first_defined(
                getattr(settings, "DRONE_SOP_DUMMY_MODE", None),
                os.getenv("DRONE_SOP_DUMMY_MODE"),
            ),
            False,
        )
        dummy_mail_messages_url = (
            getattr(settings, "DRONE_SOP_DUMMY_MAIL_MESSAGES_URL", "")
            or os.getenv("DRONE_SOP_DUMMY_MAIL_MESSAGES_URL")
            or ""
        ).strip()

        needtosend_rules_raw = getattr(settings, "DRONE_SOP_NEEDTOSEND_RULES", None)
        if needtosend_rules_raw is None:
            needtosend_rules_raw = os.getenv("DRONE_SOP_NEEDTOSEND_RULES")
        needtosend_rules = tuple(_parse_needtosend_rules(needtosend_rules_raw))

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            timeout=timeout,
            dummy_mode=dummy_mode,
            dummy_mail_messages_url=dummy_mail_messages_url,
            needtosend_rules=needtosend_rules,
        )


def _list_dummy_mail_messages(*, url: str, timeout: int) -> list[dict[str, Any]]:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages")
    if not isinstance(messages, list):
        return []
    normalized: list[dict[str, Any]] = []
    for entry in messages:
        if isinstance(entry, dict):
            normalized.append(entry)
    normalized.sort(key=lambda item: int(item.get("id") or 0))
    return normalized


def _delete_dummy_mail_messages(*, url: str, mail_ids: Sequence[int], timeout: int) -> int:
    deleted = 0
    for mail_id in mail_ids:
        resp = requests.delete(f"{url.rstrip('/')}/{mail_id}", timeout=timeout)
        if resp.status_code in {200, 204}:
            deleted += 1
    return deleted


def _upsert_drone_sop_rows(*, rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 0

    insert_cols = [
        "sop_key",
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
        "comment",
        "defect_url",
        "instant_inform",
        "needtosend",
        "custom_end_step",
    ]
    conflict_cols = ["sop_key"]
    exclude_update_cols = {"needtosend", "comment", "instant_inform", "sop_key"}

    placeholders = ",".join(["%s"] * len(insert_cols))
    quoted_table = f'"{DroneSOP._meta.db_table}"'
    quoted_insert_cols = ", ".join(f'"{col}"' for col in insert_cols)
    conflict_target = ", ".join(f'"{col}"' for col in conflict_cols)

    update_parts = [
        f'"{col}" = COALESCE(EXCLUDED."{col}", {quoted_table}."{col}")'
        for col in insert_cols
        if col not in exclude_update_cols
    ]
    update_clause = ", ".join(update_parts)

    sql = f"""
        INSERT INTO {quoted_table} ({quoted_insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_target})
        DO UPDATE SET {update_clause}
    """

    args = []
    for row in rows:
        values: list[Any] = []
        if not row.get("sop_key"):
            row["sop_key"] = build_sop_key(
                line_id=row.get("line_id"),
                eqp_id=row.get("eqp_id"),
                chamber_ids=row.get("chamber_ids"),
                lot_id=row.get("lot_id"),
                main_step=row.get("main_step"),
            )
        for col in insert_cols:
            value = row.get(col)
            if value is None and col == "instant_inform":
                value = 0
            values.append(value)
        args.append(tuple(values))
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, args)

    return len(rows)


def _prune_old_drone_sop_rows(*, days: int) -> int:
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = DroneSOP.objects.filter(created_at__lt=cutoff).delete()
    return int(deleted or 0)


def run_drone_sop_pop3_ingest_from_env() -> DroneSopPop3IngestResult:
    """Drone SOP POP3 수집을 실행합니다.

    Side effects:
        - POP3(또는 더미 메일 API)에서 메일을 읽고 삭제합니다.
        - drone_sop 테이블에 upsert 합니다.
        - 90일 초과 데이터는 정리합니다.
    """

    config = DroneSopPop3Config.from_settings()
    early_inform_map = selectors.load_drone_sop_custom_end_step_map()

    lock_id = _lock_key("drone_sop_pop3_ingest")
    acquired = _try_advisory_lock(lock_id)
    if not acquired:
        return DroneSopPop3IngestResult(skipped=True, skip_reason="already_running")

    try:
        if config.dummy_mode:
            if not config.dummy_mail_messages_url:
                raise ValueError("DRONE_SOP_DUMMY_MAIL_MESSAGES_URL 미설정")

            matched = 0
            upserted = 0
            delete_targets: list[int] = []
            messages = _list_dummy_mail_messages(url=config.dummy_mail_messages_url, timeout=config.timeout)
            for message in messages:
                subject = str(message.get("subject") or "")
                if config.subject_contains not in subject:
                    continue
                body_html = str(message.get("body_html") or message.get("body_text") or "")
                if not body_html:
                    continue
                try:
                    parsed = _build_drone_sop_row(
                        html=body_html,
                        early_inform_map=early_inform_map,
                        needtosend_rules=config.needtosend_rules,
                    )
                except Exception:
                    logger.exception("Failed to parse dummy mail id=%s subject=%r", message.get("id"), subject)
                    continue
                if not parsed:
                    continue
                matched += 1

                try:
                    upserted += _upsert_drone_sop_rows(rows=[parsed])
                except Exception:
                    logger.exception("Failed to upsert dummy mail id=%s subject=%r", message.get("id"), subject)
                    continue

                try:
                    delete_targets.append(int(message.get("id")))
                except (TypeError, ValueError):
                    continue

            if matched == 0:
                return DroneSopPop3IngestResult(
                    matched_mails=matched,
                    upserted_rows=0,
                    deleted_mails=0,
                    pruned_rows=0,
                )

            pruned = 0
            try:
                pruned = _prune_old_drone_sop_rows(days=90)
            except Exception:
                logger.exception("Failed to prune old DroneSOP rows")

            deleted = 0
            if delete_targets:
                deleted = _delete_dummy_mail_messages(
                    url=config.dummy_mail_messages_url,
                    mail_ids=delete_targets,
                    timeout=config.timeout,
                )

            return DroneSopPop3IngestResult(
                matched_mails=matched,
                upserted_rows=upserted,
                deleted_mails=deleted,
                pruned_rows=pruned,
            )

        if not config.host or not config.username or not config.password:
            raise ValueError("POP3 connection info is incomplete (host/username/password required)")

        client_cls = poplib.POP3_SSL if config.use_ssl else poplib.POP3
        client = client_cls(config.host, config.port, timeout=config.timeout)
        matched = 0
        upserted = 0
        deleted = 0

        try:
            client.user(config.username)
            client.pass_(config.password)
            num_msgs = len(client.list()[1])
            for msg_num in range(1, num_msgs + 1):
                _, lines, _ = client.retr(msg_num)
                msg = BytesParser(policy=default).parsebytes(b"\r\n".join(lines))
                subject = msg.get("Subject") or ""
                if config.subject_contains not in subject:
                    continue
                html = _extract_html_from_email(msg)
                if not html:
                    continue
                try:
                    parsed = _build_drone_sop_row(
                        html=html,
                        early_inform_map=early_inform_map,
                        needtosend_rules=config.needtosend_rules,
                    )
                except Exception:
                    logger.exception("Failed to parse POP3 message #%s subject=%r", msg_num, subject)
                    continue
                if not parsed:
                    continue
                matched += 1
                try:
                    upserted += _upsert_drone_sop_rows(rows=[parsed])
                except Exception:
                    logger.exception("Failed to upsert POP3 message #%s subject=%r", msg_num, subject)
                    continue
                try:
                    client.dele(msg_num)
                    deleted += 1
                except Exception:
                    logger.exception("Failed to mark POP3 message #%s for deletion", msg_num)

            pruned = 0
            try:
                if upserted:
                    pruned = _prune_old_drone_sop_rows(days=90)
            except Exception:
                logger.exception("Failed to prune old DroneSOP rows")

            client.quit()
            return DroneSopPop3IngestResult(
                matched_mails=matched,
                upserted_rows=upserted,
                deleted_mails=deleted,
                pruned_rows=pruned,
            )
        except Exception:
            logger.exception("Drone SOP POP3 ingest failed; rolling back POP3 deletions via rset()")
            try:
                client.rset()
            except Exception:
                logger.debug("POP3 rset failed")
            raise
        finally:
            try:
                client.quit()
            except Exception:
                pass
    finally:
        if acquired:
            _release_advisory_lock(lock_id)
