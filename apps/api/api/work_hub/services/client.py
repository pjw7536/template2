"""공식 Grist REST API만 사용하는 서버 간 HTTP client입니다."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import requests
from django.conf import settings


class GristConfigurationError(RuntimeError):
    """Grist 연결 설정이 비어 있거나 안전하지 않을 때 발생합니다."""


class GristRequestError(RuntimeError):
    """Grist API가 실패하거나 유효하지 않은 응답을 반환할 때 발생합니다."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class GristClient:
    """Portal 관리자가 발급한 API key로 Grist REST API를 호출합니다."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        connect_timeout: float,
        read_timeout: float,
        session: requests.Session | None = None,
    ) -> None:
        """endpoint와 인증값을 정규화하고 HTTP session을 준비합니다."""

        normalized_url = str(base_url or "").strip().rstrip("/")
        if not normalized_url:
            raise GristConfigurationError("Grist API URL이 설정되지 않았습니다.")
        self.base_url = normalized_url
        self.api_key = str(api_key or "").strip()
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or requests.Session()

    @classmethod
    def from_settings(cls) -> "GristClient":
        """환경 변수 또는 bootstrap 파일에서 server-to-server API key를 읽습니다."""

        api_key = str(getattr(settings, "GRIST_API_KEY", "") or "").strip()
        api_key_file = str(getattr(settings, "GRIST_API_KEY_FILE", "") or "").strip()
        if not api_key and api_key_file:
            try:
                api_key = Path(api_key_file).read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:
                raise GristConfigurationError(
                    "Grist API key 초기화 파일이 아직 준비되지 않았습니다."
                ) from exc
            except OSError as exc:
                raise GristConfigurationError(
                    "Grist API key 초기화 파일을 읽을 수 없습니다."
                ) from exc

        client = cls(
            base_url=str(getattr(settings, "GRIST_API_URL", "") or ""),
            api_key=api_key,
            connect_timeout=float(getattr(settings, "GRIST_CONNECT_TIMEOUT", 3.0)),
            read_timeout=float(getattr(settings, "GRIST_READ_TIMEOUT", 15.0)),
        )
        if not client.api_key:
            raise GristConfigurationError("Grist API key가 설정되지 않았습니다.")
        return client

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> Any:
        """credential을 로그에 남기지 않고 JSON REST API를 호출합니다."""

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            raise GristConfigurationError("Grist API 인증이 준비되지 않았습니다.")
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                params=params,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise GristRequestError("Grist API 요청 시간이 초과되었습니다.") from exc
        except requests.RequestException as exc:
            raise GristRequestError("Grist API에 연결할 수 없습니다.") from exc

        if response.status_code < 200 or response.status_code >= 300:
            retryable = response.status_code >= 500 or response.status_code in {408, 425, 429}
            raise GristRequestError(
                f"Grist API 요청이 실패했습니다. status={response.status_code}",
                retryable=retryable,
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GristRequestError(
                "Grist API가 JSON이 아닌 응답을 반환했습니다.",
                retryable=False,
            ) from exc

    def list_workspaces(self) -> list[dict[str, Any]]:
        """현재 단일 조직에서 접근 가능한 workspace와 document 목록을 반환합니다."""

        payload = self._request("GET", "/api/orgs/current/workspaces")
        if not isinstance(payload, list):
            raise GristRequestError("Grist workspace 응답 형식이 올바르지 않습니다.", retryable=False)
        return [item for item in payload if isinstance(item, dict)]

    def create_workspace(self, *, name: str) -> int:
        """현재 조직에 workspace를 만들고 숫자 ID를 반환합니다."""

        payload = self._request(
            "POST",
            "/api/orgs/current/workspaces",
            payload={"name": name},
        )
        try:
            return int(payload)
        except (TypeError, ValueError) as exc:
            raise GristRequestError("생성된 Grist workspace ID가 없습니다.", retryable=False) from exc

    def create_document(self, *, workspace_id: int, name: str) -> str:
        """workspace에 빈 document를 만들고 문자열 ID를 반환합니다."""

        payload = self._request(
            "POST",
            f"/api/workspaces/{workspace_id}/docs",
            payload={"name": name},
        )
        doc_id = str(payload or "").strip()
        if not doc_id:
            raise GristRequestError("생성된 Grist document ID가 없습니다.", retryable=False)
        return doc_id

    def list_tables(self, *, doc_id: str) -> list[dict[str, Any]]:
        """document의 table metadata를 반환합니다."""

        payload = self._request("GET", f"/api/docs/{doc_id}/tables")
        tables = payload.get("tables", []) if isinstance(payload, dict) else []
        if not isinstance(tables, list):
            raise GristRequestError("Grist table 응답 형식이 올바르지 않습니다.", retryable=False)
        return [item for item in tables if isinstance(item, dict)]

    def create_tables(self, *, doc_id: str, tables: Sequence[Mapping[str, Any]]) -> None:
        """document에 table과 초기 column을 일괄 생성합니다."""

        self._request(
            "POST",
            f"/api/docs/{doc_id}/tables",
            payload={"tables": list(tables)},
        )

    def delete_table(self, *, doc_id: str, table_id: str) -> None:
        """새 demo document에 자동 생성된 빈 table을 제거합니다."""

        # Grist table API에는 DELETE route가 없으므로 공식 apply endpoint에
        # 사용자 action을 전달합니다.
        self._request(
            "POST",
            f"/api/docs/{doc_id}/apply",
            payload=[["RemoveTable", table_id]],
        )

    def list_columns(self, *, doc_id: str, table_id: str) -> list[dict[str, Any]]:
        """table의 column schema를 반환합니다."""

        payload = self._request(
            "GET",
            f"/api/docs/{doc_id}/tables/{table_id}/columns",
        )
        columns = payload.get("columns", []) if isinstance(payload, dict) else []
        if not isinstance(columns, list):
            raise GristRequestError("Grist column 응답 형식이 올바르지 않습니다.", retryable=False)
        return [item for item in columns if isinstance(item, dict)]

    def create_columns(
        self,
        *,
        doc_id: str,
        table_id: str,
        columns: Sequence[Mapping[str, Any]],
    ) -> None:
        """table에 누락된 column을 추가합니다."""

        self._request(
            "POST",
            f"/api/docs/{doc_id}/tables/{table_id}/columns",
            payload={"columns": list(columns)},
        )

    def iter_records(
        self,
        *,
        doc_id: str,
        table_id: str,
        filters: Mapping[str, Sequence[Any]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """선택한 filter에 맞는 table record를 field와 ID가 평탄화된 형태로 순회합니다."""

        params = (
            {
                "filter": json.dumps(
                    dict(filters),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            }
            if filters
            else None
        )
        payload = self._request(
            "GET",
            f"/api/docs/{doc_id}/tables/{table_id}/records",
            params=params,
        )
        records = payload.get("records", []) if isinstance(payload, dict) else []
        if not isinstance(records, list):
            raise GristRequestError("Grist record 응답 형식이 올바르지 않습니다.", retryable=False)
        for record in records:
            if not isinstance(record, dict):
                continue
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            yield {"id": record.get("id"), **fields}

    def find_record_by_field(
        self,
        *,
        doc_id: str,
        table_id: str,
        field_name: str,
        value: str,
    ) -> dict[str, Any] | None:
        """field exact 값이 일치하는 첫 record를 반환합니다."""

        for record in self.iter_records(
            doc_id=doc_id,
            table_id=table_id,
            filters={field_name: [value]},
        ):
            if str(record.get(field_name) or "") == str(value):
                return record
        return None

    def create_record(
        self,
        *,
        doc_id: str,
        table_id: str,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Grist table에 record를 하나 생성합니다."""

        payload = self._request(
            "POST",
            f"/api/docs/{doc_id}/tables/{table_id}/records",
            payload={"records": [{"fields": dict(values)}]},
        )
        records = payload.get("records", []) if isinstance(payload, dict) else []
        if not records or not isinstance(records[0], dict) or not records[0].get("id"):
            raise GristRequestError("생성된 Grist record ID가 없습니다.", retryable=False)
        return {"id": records[0]["id"], **dict(values)}

    def update_record(
        self,
        *,
        doc_id: str,
        table_id: str,
        row_id: int,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Grist record 일부 field를 수정합니다."""

        self._request(
            "PATCH",
            f"/api/docs/{doc_id}/tables/{table_id}/records",
            payload={"records": [{"id": row_id, "fields": dict(values)}]},
        )
        return {"id": row_id, **dict(values)}

    def get_document_access(self, *, doc_id: str) -> dict[str, Any]:
        """document에 명시된 사용자별 접근 권한을 반환합니다."""

        payload = self._request("GET", f"/api/docs/{doc_id}/access")
        if not isinstance(payload, dict):
            raise GristRequestError("Grist access 응답 형식이 올바르지 않습니다.", retryable=False)
        return payload

    def update_document_access(
        self,
        *,
        doc_id: str,
        users: Mapping[str, str | None],
        max_inherited_role: str | None,
    ) -> None:
        """상속 상한과 email별 document role 변경분을 함께 적용합니다."""

        self._request(
            "PATCH",
            f"/api/docs/{doc_id}/access",
            payload={
                "delta": {
                    "maxInheritedRole": max_inherited_role,
                    "users": dict(users),
                }
            },
        )

    def list_webhooks(self, *, doc_id: str) -> list[dict[str, Any]]:
        """document에 설정된 Webhook 목록을 반환합니다."""

        payload = self._request("GET", f"/api/docs/{doc_id}/webhooks")
        webhooks = payload.get("webhooks", []) if isinstance(payload, dict) else []
        if not isinstance(webhooks, list):
            raise GristRequestError("Grist Webhook 응답 형식이 올바르지 않습니다.", retryable=False)
        return [item for item in webhooks if isinstance(item, dict)]

    def create_webhook(
        self,
        *,
        doc_id: str,
        name: str,
        table_id: str,
        url: str,
        authorization: str,
    ) -> None:
        """WorkLog add/update를 전송하는 Webhook을 생성합니다."""

        self._request(
            "POST",
            f"/api/docs/{doc_id}/webhooks",
            payload={
                "webhooks": [
                    {
                        "fields": {
                            "name": name,
                            "memo": "Portal WorkLog 후속 조치 Task 동기화",
                            "url": url,
                            "authorization": authorization,
                            "enabled": True,
                            "eventTypes": ["add", "update"],
                            "isReadyColumn": None,
                            "tableId": table_id,
                        }
                    }
                ]
            },
        )

    def update_webhook(
        self,
        *,
        doc_id: str,
        webhook_id: str,
        url: str,
        authorization: str,
    ) -> None:
        """기존 Webhook의 callback URL과 인증값을 원하는 상태로 갱신합니다."""

        self._request(
            "PATCH",
            f"/api/docs/{doc_id}/webhooks/{webhook_id}",
            payload={"url": url, "authorization": authorization},
        )
