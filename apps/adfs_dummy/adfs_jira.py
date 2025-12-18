"""Jira sandbox endpoints for local testing."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Body

from adfs_stores import jira_store

router = APIRouter()


@router.get("/jira/issues")
async def list_dummy_jira_issues() -> Dict[str, Any]:
    """Return all dummy Jira issues for quick inspection."""

    issues = list(jira_store.issues.values())
    issues.sort(key=lambda item: int(item.get("id") or 0))
    return {"count": len(issues), "issues": issues}


@router.post("/jira/rest/api/2/issue", status_code=201)
async def create_dummy_jira_issue(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Simulate Jira single issue create (POST /rest/api/2/issue)."""

    fields = payload.get("fields")
    if not isinstance(fields, dict):
        fields = {}

    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    project_key = str(project.get("key") or "DUMMY").strip() or "DUMMY"

    issue = jira_store.create_issue(project_key=project_key, fields=fields)
    return {"id": issue["id"], "key": issue["key"], "self": issue["self"]}


@router.post("/jira/rest/api/2/issue/bulk", status_code=201)
async def bulk_create_dummy_jira_issues(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Simulate Jira bulk create (POST /rest/api/2/issue/bulk)."""

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
    """Reset dummy Jira issues to empty."""

    jira_store.reset()
    return {"status": "ok", "count": 0}
