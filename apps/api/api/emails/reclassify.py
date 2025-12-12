from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone

from api.common.affiliations import UNCLASSIFIED_USER_SDWT_PROD, resolve_user_affiliation
from api.emails.services import register_email_to_rag
from api.models import Email, UserSdwtProdChange

logger = logging.getLogger(__name__)


def reclassify_emails_for_user_sdwt_change(user, effective_from: Optional[datetime]) -> int:
    """
    user_sdwt_prod 변경 시점 이후 메일을 새 소속으로 재분류하고 RAG 재색인한다.
    - 대상: sender_id == user.username 인 메일
    - 범위: effective_from 이상, 다음 변경 시점 이전 (있으면)
    """
    if effective_from is None:
        effective_from = timezone.now()

    next_change: Optional[UserSdwtProdChange] = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=effective_from)
        .order_by("effective_from")
        .first()
    )

    start = effective_from
    end = next_change.effective_from if next_change else None

    qs = Email.objects.filter(sender_id=user.username, received_at__gte=start)
    if end is not None:
        qs = qs.filter(received_at__lt=end)

    previous_user_sdwt = {row["id"]: row["user_sdwt_prod"] for row in qs.values("id", "user_sdwt_prod")}
    ids = list(previous_user_sdwt.keys())
    if not ids:
        return 0

    affiliation = resolve_user_affiliation(user, effective_from)
    user_sdwt_prod = affiliation.get("user_sdwt_prod") or UNCLASSIFIED_USER_SDWT_PROD

    with transaction.atomic():
        Email.objects.filter(id__in=ids).update(
            user_sdwt_prod=user_sdwt_prod,
        )

        # RAG 재색인
        for email in Email.objects.filter(id__in=ids).iterator():
            email.user_sdwt_prod = user_sdwt_prod
            try:
                register_email_to_rag(
                    email,
                    previous_user_sdwt_prod=previous_user_sdwt.get(email.id),
                    persist_fields=["user_sdwt_prod", "rag_doc_id"],
                )
            except Exception:
                logger.exception("Failed to reinsert RAG for email id=%s", email.id)

    return len(ids)
