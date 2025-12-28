"""로컬 테스트를 위한 Jira 샌드박스 엔드포인트입니다."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Body

from adfs_stores import jira_store

router = APIRouter()


@router.get("/jira/issues")
async def list_dummy_jira_issues() -> Dict[str, Any]:
    """빠른 점검을 위해 더미 Jira 이슈를 모두 반환합니다."""

    issues = list(jira_store.issues.values())
    issues.sort(key=lambda item: int(item.get("id") or 0))
    return {"count": len(issues), "issues": issues}


@router.post("/jira/rest/api/2/issue", status_code=201)
async def create_dummy_jira_issue(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Jira 단건 이슈 생성(POST /rest/api/2/issue)을 모사합니다."""

    fields = payload.get("fields")
    if not isinstance(fields, dict):
        fields = {}

    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    project_key = str(project.get("key") or "DUMMY").strip() or "DUMMY"

    issue = jira_store.create_issue(project_key=project_key, fields=fields)
    return {"id": issue["id"], "key": issue["key"], "self": issue["self"]}


@router.post("/jira/rest/api/2/issue/bulk", status_code=201)
async def bulk_create_dummy_jira_issues(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Jira 대량 생성(POST /rest/api/2/issue/bulk)을 모사합니다."""

    updates = payload.get("issueUpdates")
    if not isinstance(updates, list):
        updates = []

    issues: List[Dict[str, str]] = []
    for entry in updates:
        if not isinstance(entry, dict):
            continue
        fields = entry.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
        project_key = str(project.get("key") or "DUMMY").strip() or "DUMMY"
        issue = jira_store.create_issue(project_key=project_key, fields=fields)
        issues.append({"id": issue["id"], "key": issue["key"], "self": issue["self"]})

    return {"issues": issues}


@router.post("/jira/reset")
async def reset_dummy_jira() -> Dict[str, Any]:
    """더미 Jira 이슈를 비워 초기화합니다."""

    jira_store.reset()
    return {"status": "ok", "count": 0}
