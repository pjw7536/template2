import json
import requests
from django.conf import settings

RAG_INSERT_URL = getattr(settings, "RAG_INSERT_URL", "")
RAG_DELETE_URL = getattr(settings, "RAG_DELETE_URL", "")
RAG_INDEX_NAME = getattr(settings, "RAG_INDEX_NAME", "")
RAG_HEADERS = {
    "Content-Type": "application/json",
    "x-dep-ticket": getattr(settings, "RAG_PASS_KEY", ""),
    "api-key": getattr(settings, "RAG_API_KEY", ""),
}


def insert_email_to_rag(email):
    """Email 모델을 RAG 인덱스에 등록."""

    payload = {
        "index_name": RAG_INDEX_NAME,
        "data": {
            "doc_id": email.rag_doc_id,
            "title": email.subject,
            "content": email.body_text or "",
            "permission_groups": ["rag-public"],
            "created_time": email.received_at.isoformat(),
            "email_id": email.id,
            "sender": email.sender,
            "recipient": email.recipient,
            "received_at": email.received_at.isoformat(),
        },
        "chunk_factor": {
            "logic": "fixed_size",
            "chunk_size": 300,
            "chunk_overlap": 80,
            "separator": " ",
        },
    }
    resp = requests.post(
        RAG_INSERT_URL,
        headers=RAG_HEADERS,
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()


def delete_rag_doc(doc_id: str):
    """RAG에서 doc_id에 해당하는 문서를 삭제."""

    payload = {
        "index_name": RAG_INDEX_NAME,
        "permission_groups": ["rag-public"],
        "doc_id": doc_id,
    }
    resp = requests.post(
        RAG_DELETE_URL,
        headers=RAG_HEADERS,
        data=json.dumps(payload),
        timeout=10,
    )
    resp.raise_for_status()
