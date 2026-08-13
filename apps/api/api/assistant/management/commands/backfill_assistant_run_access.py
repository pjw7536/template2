# =============================================================================
# 명령: Assistant legacy Run/access provenance backfill
# 주요 옵션: --dry-run, --batch-size, --checkpoint, --checkpoint-file
# 핵심 전제: 해석 불가능한 데이터는 삭제하지 않고 legacy-unresolved로 잠급니다.
# =============================================================================
"""legacy Assistant 메시지를 재실행 가능한 batch 단위로 분류하고 Run에 연결합니다."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from api.assistant.models import (
    AssistantConversation,
    AssistantGeneration,
    AssistantMessage,
)
from api.assistant.services.access_requirements import (
    access_requirements_for_scopes,
    merge_access_requirements,
    normalize_access_requirements,
)

PROFILE_METADATA = {
    "portal-default": {
        "provider": "openwebui",
        "partition": "shared",
        "scopes": ("assistant",),
    },
    "email-rag": {
        "provider": "email-rag",
        "partition": "scope:emails",
        "scopes": ("assistant", "emails"),
    },
    "observer-analysis": {
        "provider": "observer-analysis",
        "partition": "scope:observer",
        "scopes": ("assistant", "observer"),
    },
}


def _classify_message(message: AssistantMessage) -> str:
    """보존된 고신뢰 provenance를 우선해 legacy Profile을 단일 분류합니다."""

    generation = message.generation
    stored_profile = str(getattr(generation, "profile_key", "") or "")
    provider = str(getattr(generation, "provider", "") or "").lower()
    if stored_profile == "legacy-unresolved" or provider == "legacy-unresolved":
        return "legacy-unresolved"
    snapshot = message.context_snapshot
    has_observer_snapshot = snapshot is not None and snapshot.kind == "observer"
    has_email_evidence = bool(
        message.sources
        or message.user_sdwt_prod
        or message.context_key == "assistant"
    )
    if has_observer_snapshot and has_email_evidence:
        return "legacy-unresolved"
    if has_observer_snapshot:
        return "observer-analysis"
    if has_email_evidence:
        return "email-rag"
    if stored_profile in PROFILE_METADATA:
        return stored_profile
    provider_profiles = {
        "openwebui": "portal-default",
        "email-rag": "email-rag",
        "observer-analysis": "observer-analysis",
    }
    if provider in provider_profiles:
        return provider_profiles[provider]
    context_key = str(message.context_key or "")
    if context_key.startswith("observer:"):
        return "observer-analysis"
    if context_key == "assistant:openwebui" or context_key.startswith(
        "assistant:openwebui:"
    ):
        return "portal-default"
    return "legacy-unresolved"


def _is_unresolved(requirements: object) -> bool:
    """요구사항에 migration sentinel이 남아 있는지 반환합니다."""

    normalized = normalize_access_requirements(requirements)
    return "legacy-unresolved" in normalized["accountScopes"]


def _merge_backfill_requirements(
    existing: object,
    classified: object,
) -> dict[str, object]:
    """migration sentinel은 교체하고 실제 분류 요구사항끼리만 합칩니다."""

    if _is_unresolved(existing):
        return normalize_access_requirements(classified)
    return merge_access_requirements(existing, classified)


def _needs_backfill(message: AssistantMessage) -> bool:
    """새 Runtime v2 row를 건드리지 않고 legacy 또는 잠긴 row만 선택합니다."""

    generation = message.generation
    if generation is not None and (
        generation.profile_key == "legacy-unresolved"
        or generation.provider == "legacy-unresolved"
    ):
        return False
    return bool(
        _is_unresolved(message.access_requirements)
        or generation is None
        or not str(generation.profile_key or "").strip()
        or generation.profile_key == "legacy-unresolved"
        or _is_unresolved(generation.access_requirements)
    )


def _requirements_for_message(
    message: AssistantMessage,
    *,
    profile_key: str,
) -> dict[str, object]:
    """분류 결과와 저장 source에서 보수적인 access requirements를 만듭니다."""

    if profile_key == "legacy-unresolved":
        return {
            "version": 1,
            "accountScopes": ["legacy-unresolved"],
            "dataClaims": {},
        }
    metadata = PROFILE_METADATA[profile_key]
    groups = {message.user_sdwt_prod} if message.user_sdwt_prod else set()
    mailboxes: set[str] = (
        {message.user_sdwt_prod} if message.user_sdwt_prod else set()
    )
    for source in message.sources if isinstance(message.sources, list) else []:
        if not isinstance(source, dict):
            continue
        for key in ("permissionGroup", "permission_group", "userSdwtProd", "user_sdwt_prod"):
            value = str(source.get(key) or "").strip()
            if value:
                groups.add(value)
        mailbox = str(source.get("mailbox") or "").strip()
        if mailbox:
            mailboxes.add(mailbox)
    return merge_access_requirements(
        access_requirements_for_scopes(metadata["scopes"]),
        {
            "version": 1,
            "accountScopes": [],
            "dataClaims": {
                "ragPermissionGroups": sorted(groups),
                "mailboxes": sorted(mailboxes),
            },
        },
    )


def _synthetic_client_request_id(message: AssistantMessage) -> str:
    """user/conversation/anchor 기반 결정적 synthetic Run ID를 반환합니다."""

    raw = f"{message.conversation.user_id}:{message.conversation_id}:{message.id}"
    return f"legacy-{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


class Command(BaseCommand):
    """Assistant legacy provenance를 batch 단위로 backfill합니다."""

    help = "Assistant legacy 메시지와 Run의 Profile/access provenance를 backfill합니다."

    def add_arguments(self, parser: CommandParser) -> None:
        """dry-run, batch와 resume option을 등록합니다."""

        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--checkpoint", type=int, default=0)
        parser.add_argument("--checkpoint-file", type=str, default="")

    def handle(self, *args: Any, **options: Any) -> None:
        """checkpoint 이후 메시지를 처리하고 분류·충돌·미해결 보고서를 출력합니다."""

        del args
        dry_run = bool(options["dry_run"])
        batch_size = max(1, min(int(options["batch_size"]), 5000))
        checkpoint_path = Path(options["checkpoint_file"]) if options["checkpoint_file"] else None
        checkpoint = max(0, int(options["checkpoint"]))
        if checkpoint_path is not None and checkpoint_path.exists():
            checkpoint = max(checkpoint, int(checkpoint_path.read_text().strip() or 0))

        counts: Counter[str] = Counter()
        last_id = checkpoint
        while True:
            messages = list(
                AssistantMessage.objects.filter(id__gt=last_id)
                .select_related("conversation", "conversation__user", "generation", "context_snapshot")
                .order_by("id")[:batch_size]
            )
            if not messages:
                break
            with transaction.atomic():
                for message in messages:
                    if not _needs_backfill(message):
                        last_id = message.id
                        continue
                    profile_key = _classify_message(message)
                    counts[profile_key] += 1
                    requirements = _requirements_for_message(
                        message,
                        profile_key=profile_key,
                    )
                    if not dry_run:
                        generation = message.generation
                        if (
                            generation is None
                            and message.role == AssistantMessage.Roles.ASSISTANT
                            and message.parent_id is not None
                        ):
                            parent = AssistantMessage.objects.filter(
                                id=message.parent_id,
                                conversation=message.conversation,
                            ).select_related("generation").first()
                            if parent is not None:
                                generation = parent.generation
                        if generation is None:
                            metadata = PROFILE_METADATA.get(profile_key, {})
                            generation, _ = AssistantGeneration.objects.get_or_create(
                                user=message.conversation.user,
                                client_request_id=_synthetic_client_request_id(message),
                                defaults={
                                    "conversation": message.conversation,
                                    "context_key": message.context_key,
                                    "status": AssistantGeneration.Status.COMPLETED,
                                    "provider": metadata.get("provider", "legacy-unresolved"),
                                    "profile_key": profile_key,
                                    "profile_version": 1 if metadata else None,
                                    "memory_partition": metadata.get("partition", "legacy-unresolved"),
                                    "access_requirements": requirements,
                                    "request_hash": "",
                                    "expires_at": timezone.now() + timedelta(seconds=1),
                                    "started_at": message.created_at,
                                    "finished_at": message.created_at,
                                },
                            )
                            message.generation = generation
                        else:
                            metadata = PROFILE_METADATA.get(profile_key, {})
                            generation.profile_key = profile_key
                            generation.profile_version = 1 if metadata else None
                            generation.memory_partition = metadata.get(
                                "partition", "legacy-unresolved"
                            )
                            generation.access_requirements = _merge_backfill_requirements(
                                generation.access_requirements,
                                requirements,
                            )
                            generation.save(
                                update_fields=[
                                    "profile_key",
                                    "profile_version",
                                    "memory_partition",
                                    "access_requirements",
                                    "updated_at",
                                ]
                            )
                        message.access_requirements = requirements
                        message.save(
                            update_fields=["generation", "access_requirements"]
                        )
                        generation.messages.update(
                            access_requirements=generation.access_requirements
                        )
                        message.access_requirements = generation.access_requirements
                    last_id = message.id
                if dry_run:
                    transaction.set_rollback(True)
            if checkpoint_path is not None and not dry_run:
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                checkpoint_path.write_text(str(last_id), encoding="utf-8")

        if not dry_run:
            for conversation in AssistantConversation.objects.all().iterator(
                chunk_size=batch_size
            ):
                message_requirements = list(
                    conversation.messages.values_list(
                        "access_requirements", flat=True
                    )
                )
                conversation.title_access_requirements = (
                    merge_access_requirements(*message_requirements)
                    if message_requirements
                    else {
                        "version": 1,
                        "accountScopes": ["legacy-unresolved"],
                        "dataClaims": {},
                    }
                )
                conversation.save(update_fields=["title_access_requirements"])
                for summary in conversation.summaries.all():
                    context_key = str(summary.context_key or "")
                    if context_key.startswith("observer:"):
                        summary.memory_partition = "scope:observer"
                    elif context_key == "assistant":
                        summary.memory_partition = "scope:emails"
                    elif context_key == "chatwidget:shared" or context_key.startswith(
                        "assistant:openwebui"
                    ):
                        summary.memory_partition = "shared"
                    else:
                        summary.memory_partition = "legacy-unresolved"
                    partition_requirements = [
                        message.access_requirements
                        for message in conversation.messages.select_related(
                            "generation"
                        ).all()
                        if str(
                            getattr(message.generation, "memory_partition", "")
                            or "legacy-unresolved"
                        )
                        == summary.memory_partition
                    ]
                    summary.access_requirements = (
                        merge_access_requirements(*partition_requirements)
                        if partition_requirements
                        else {
                            "version": 1,
                            "accountScopes": ["legacy-unresolved"],
                            "dataClaims": {},
                        }
                    )
                    summary.save(
                        update_fields=["memory_partition", "access_requirements"]
                    )

        report = {
            "dryRun": dry_run,
            "checkpoint": last_id,
            "classified": {
                key: counts[key] for key in sorted(PROFILE_METADATA)
            },
            "unresolved": counts["legacy-unresolved"],
            "processed": sum(counts.values()),
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
