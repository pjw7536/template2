"""Emails feature service facade."""

from __future__ import annotations

from .ingest import _parse_message_to_fields, ingest_pop3_mailbox, run_pop3_ingest, run_pop3_ingest_from_env
from .mail_api import MailSendError, requests, send_knox_mail_api
from .mailbox import get_mailbox_access_summary_for_user
from .mutations import (
    SENT_MAILBOX_ID,
    bulk_delete_emails,
    claim_unassigned_emails_for_user,
    delete_single_email,
    move_emails_for_user,
    move_emails_to_user_sdwt_prod,
    move_sender_emails_after,
)
from .query_filters import (
    build_email_filters,
    parse_datetime_value,
    parse_int,
    parse_mailbox_user_sdwt_prod,
)
from .rag import (
    enqueue_email_outbox,
    enqueue_rag_delete,
    enqueue_rag_index,
    enqueue_rag_index_for_emails,
    process_email_outbox_batch,
    register_email_to_rag,
    register_missing_rag_docs,
)
from .rag_exports import (
    RAG_INDEX_EMAILS,
    RAG_PUBLIC_GROUP,
    delete_rag_doc,
    insert_email_to_rag,
    resolve_rag_index_name,
)
from .storage import gzip_body, save_parsed_email

__all__ = [
    "MailSendError",
    "RAG_INDEX_EMAILS",
    "RAG_PUBLIC_GROUP",
    "SENT_MAILBOX_ID",
    "_parse_message_to_fields",
    "bulk_delete_emails",
    "build_email_filters",
    "claim_unassigned_emails_for_user",
    "delete_rag_doc",
    "delete_single_email",
    "enqueue_email_outbox",
    "enqueue_rag_delete",
    "enqueue_rag_index",
    "enqueue_rag_index_for_emails",
    "get_mailbox_access_summary_for_user",
    "gzip_body",
    "ingest_pop3_mailbox",
    "insert_email_to_rag",
    "move_emails_for_user",
    "move_emails_to_user_sdwt_prod",
    "move_sender_emails_after",
    "parse_datetime_value",
    "parse_int",
    "parse_mailbox_user_sdwt_prod",
    "process_email_outbox_batch",
    "register_email_to_rag",
    "register_missing_rag_docs",
    "requests",
    "resolve_rag_index_name",
    "run_pop3_ingest",
    "run_pop3_ingest_from_env",
    "save_parsed_email",
    "send_knox_mail_api",
]
