import json
from typing import List

import requests
from django.conf import settings

RAG_SEARCH_URL = getattr(settings, "RAG_SEARCH_URL", "")
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
            "department_code": email.department_code,
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


def search_rag_by_department(query_text: str, department_codes: List[str], num_result_doc: int = 5):
    """
    department_code 필터를 적용하여 RAG 문서를 검색하는 예시 함수.
    - 모든 검색 요청은 department_code 필터를 포함해야 한다.
    """

    if not RAG_SEARCH_URL:
        raise ValueError("RAG_SEARCH_URL is not configured")

    payload = {
        "index_name": RAG_INDEX_NAME,
        "permission_groups": ["rag-public"],
        "query_text": query_text,
        "num_result_doc": num_result_doc,
        "filter": {
            "department_code": department_codes,
        },
    }
    resp = requests.post(
        RAG_SEARCH_URL,
        headers=RAG_HEADERS,
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
