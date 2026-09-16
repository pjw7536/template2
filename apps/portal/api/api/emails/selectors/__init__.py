# =============================================================================
# 모듈 설명: Emails selector의 명시적 public facade입니다.
# =============================================================================

from .assistant import resolve_assistant_email_scope
from .assets import (
    build_email_ocr_text,
    get_email_asset_by_email_and_sequence,
    get_email_asset_by_id,
    has_unprocessed_email_assets,
    list_claimable_email_assets,
    list_claimable_email_assets_for_update,
    list_email_asset_keys_by_email_ids,
    list_email_assets_by_email_ids,
)
from .lists import (
    get_email_by_id,
    get_filtered_emails,
    get_sent_emails,
    list_distinct_email_mailboxes,
    list_emails_by_ids,
    list_privileged_email_mailboxes,
)
from .mailboxes import (
    EmailAffiliation,
    count_unassigned_emails_for_sender_id,
    get_accessible_user_sdwt_prods_for_user,
    list_mailbox_members,
    list_unassigned_email_ids_for_sender_id,
    resolve_email_affiliation,
    resolve_sender_id_from_user,
)
from .mutations import (
    get_email_for_update,
    list_emails_for_update,
    user_can_bulk_delete_emails,
)
from .outbox import (
    list_email_id_user_sdwt_by_ids,
    list_email_ids_by_sender_after,
    list_pending_email_outbox,
    list_pending_rag_emails,
)

__all__ = [
    "EmailAffiliation",
    "build_email_ocr_text",
    "count_unassigned_emails_for_sender_id",
    "get_accessible_user_sdwt_prods_for_user",
    "get_email_asset_by_email_and_sequence",
    "get_email_asset_by_id",
    "get_email_by_id",
    "get_email_for_update",
    "get_filtered_emails",
    "get_sent_emails",
    "has_unprocessed_email_assets",
    "list_claimable_email_assets",
    "list_claimable_email_assets_for_update",
    "list_distinct_email_mailboxes",
    "list_email_asset_keys_by_email_ids",
    "list_email_assets_by_email_ids",
    "list_email_id_user_sdwt_by_ids",
    "list_email_ids_by_sender_after",
    "list_emails_by_ids",
    "list_emails_for_update",
    "list_mailbox_members",
    "list_pending_email_outbox",
    "list_pending_rag_emails",
    "list_privileged_email_mailboxes",
    "list_unassigned_email_ids_for_sender_id",
    "resolve_assistant_email_scope",
    "resolve_email_affiliation",
    "resolve_sender_id_from_user",
    "user_can_bulk_delete_emails",
]
