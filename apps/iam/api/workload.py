"""IAM의 월별 업무 부하를 저장하는 WSGI 애플리케이션입니다."""

import json
import logging
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from wsgiref.simple_server import make_server

import jwt

METRICS = ("equipment", "spc", "fdc", "apc", "pm", "lotHold")
DIFFICULTIES = ("낮음", "보통", "높음")
MONTH_PATH = re.compile(r"/api/workload/([1-9][0-9]{3}-(?:0[1-9]|1[0-2]))")
HEALTH_PATH = "/api/workload/healthz"
MAX_BODY = 4 * 1024 * 1024


class RequestError(Exception):
    """클라이언트에 표시할 HTTP 오류입니다."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def keycloak_authorizer(issuer, client_id):
    """IAM에서 발급된 플랫폼 관리자 액세스 토큰을 검증합니다."""
    jwks = jwt.PyJWKClient(f"{issuer}/protocol/openid-connect/certs", timeout=5)

    def authorize(authorization):
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise RequestError("401 Unauthorized", "IAM 로그인이 필요합니다.")
        try:
            key = jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=issuer,
                audience="realm-management",
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            )
        except jwt.PyJWKClientConnectionError as error:
            raise RequestError("503 Service Unavailable", "Keycloak에 연결할 수 없습니다.") from error
        except jwt.PyJWTError as error:
            raise RequestError("401 Unauthorized", "IAM 로그인 토큰이 유효하지 않습니다.") from error

        roles = claims.get("resource_access", {}).get("realm-management", {}).get("roles", [])
        if (
            claims.get("azp") != client_id
            or claims.get("typ") != "Bearer"
            or not isinstance(roles, list)
            or "manage-users" not in roles
        ):
            raise RequestError("403 Forbidden", "IAM 관리자 권한이 필요합니다.")

    return authorize


def number(value, maximum, *, integer=False):
    allowed = (int,) if integer else (int, float)
    return type(value) in allowed and 0 <= value <= maximum


def bounded_text(value, maximum, *, empty=False):
    return isinstance(value, str) and len(value) <= maximum and (empty or bool(value.strip()))


def read_payload(environ):
    """월별 가중치와 라인 기록을 확인한 뒤 저장할 필드만 반환합니다."""
    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
        if size > MAX_BODY:
            raise RequestError("413 Content Too Large", "저장할 기록의 용량이 너무 큽니다.")
        if size < 1:
            raise ValueError
        payload = json.loads(environ["wsgi.input"].read(size))
    except (ValueError, UnicodeError) as error:
        raise RequestError("400 Bad Request", "저장 데이터 형식이 올바르지 않습니다.") from error

    error = RequestError("400 Bad Request", "가중치, 배치 인원, 발생 건수 또는 근무시간을 확인하세요.")
    invalid_sci = RequestError("400 Bad Request", "SCI 점수는 0 이상의 숫자로 입력하세요.")
    invalid_totals = RequestError("400 Bad Request", "월 전체 클릭 수와 WF Move는 0 이상의 정수로 입력하세요.")
    if not isinstance(payload, dict) or not number(payload.get("revision"), 2**53 - 1, integer=True):
        raise error

    weights = payload.get("weights")
    if not isinstance(weights, dict) or set(weights) != set(METRICS):
        raise error
    if not all(number(weight, 1000) for weight in weights.values()) or not any(weights.values()):
        raise error

    records = payload.get("records")
    if not isinstance(records, list):
        raise error

    clean_records = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise error
        names = ("teamId", "team", "lineId", "line")
        if not all(bounded_text(record.get(key), 255) for key in names):
            raise error
        identity = (record["teamId"], record["lineId"])
        if identity in seen or not number(record.get("headcount"), 1_000_000, integer=True):
            raise error
        if not all(number(record.get(key), 1_000_000, integer=True) for key in METRICS):
            raise error
        hours = record.get("averageHours")
        if hours is not None and not number(hours, 744):
            raise error
        sci_score = record.get("sciScore")
        if sci_score is not None and not number(sci_score, 2**53 - 1):
            raise invalid_sci
        totals = {key: record.get(key) for key in ("totalClicks", "totalWfMoves")}
        if any(value is not None and not number(value, 2**53 - 1, integer=True) for value in totals.values()):
            raise invalid_totals
        if record.get("difficulty") not in (*DIFFICULTIES, "") or not bounded_text(record.get("notes"), 1000, empty=True):
            raise error

        seen.add(identity)
        clean_record = {key: record[key] for key in (*names, "headcount", *METRICS, "difficulty", "notes")} | {
            "averageHours": hours,
            "sciScore": sci_score,
            **totals,
        }
        # 이전 기록의 1인 평균은 원래 값으로 보관합니다.
        clicks_per_person = record.get("clicksPerPerson")
        if clicks_per_person is not None and number(clicks_per_person, 2**53 - 1):
            clean_record["clicksPerPerson"] = clicks_per_person
        clean_records.append(clean_record)

    return payload["revision"], {"weights": weights, "records": clean_records}


def create_app(database, authorize):
    """DB에 월별 기록을 저장하고 revision으로 동시 수정을 확인합니다."""
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS workload_month ("
            "month TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)"
        )

    def app(environ, start_response):
        status = "200 OK"
        path = environ["PATH_INFO"]
        method = environ["REQUEST_METHOD"]
        try:
            match = MONTH_PATH.fullmatch(path)
            health = path == HEALTH_PATH
            if health:
                if method != "GET":
                    raise RequestError("405 Method Not Allowed", "지원하지 않는 요청입니다.")
            else:
                if not match:
                    raise RequestError("404 Not Found", "업무 부하 주소를 확인하세요.")
                if method not in {"GET", "PUT"}:
                    raise RequestError("405 Method Not Allowed", "지원하지 않는 요청입니다.")
                authorize(environ.get("HTTP_AUTHORIZATION", ""))
            with closing(sqlite3.connect(database)) as connection, connection:
                if health:
                    connection.execute("SELECT 1 FROM workload_month LIMIT 1").fetchone()
                    result = {"status": "ok"}
                elif method == "GET":
                    row = connection.execute(
                        "SELECT revision, payload FROM workload_month WHERE month = ?", (match.group(1),)
                    ).fetchone()
                    result = {"revision": row[0], **json.loads(row[1])} if row else {"revision": 0, "records": []}
                else:
                    month = match.group(1)
                    revision, payload = read_payload(environ)
                    serialized = json.dumps(payload, ensure_ascii=False)
                    # 다른 관리자가 같은 월을 먼저 저장했으면 입력을 덮어쓰지 않습니다.
                    if revision == 0:
                        changed = connection.execute(
                            "INSERT OR IGNORE INTO workload_month VALUES (?, 1, ?)", (month, serialized)
                        )
                    else:
                        changed = connection.execute(
                            "UPDATE workload_month SET revision = revision + 1, payload = ? "
                            "WHERE month = ? AND revision = ?", (serialized, month, revision)
                        )
                    if not changed.rowcount:
                        raise RequestError("409 Conflict", "다른 곳에서 이 달의 기록이 변경되었습니다. 다시 불러오세요.")
                    result = {"revision": revision + 1, **payload}
        except RequestError as error:
            status, result = error.status, {"error": str(error)}
        except sqlite3.Error:
            logging.exception("IAM 업무 부하 DB 요청 실패")
            status, result = "500 Internal Server Error", {"error": "업무 부하 저장소를 열 수 없습니다."}

        body = json.dumps(result, ensure_ascii=False).encode()
        start_response(status, [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ])
        return [body]

    return app


def application_from_env():
    """실행 환경에서 저장 위치와 Keycloak 발급자 주소를 읽습니다."""
    return create_app(
        os.environ["IAM_WORKLOAD_DB"],
        keycloak_authorizer(os.environ["IAM_KEYCLOAK_ISSUER"].rstrip("/"), os.getenv("IAM_KEYCLOAK_CLIENT_ID", "iam")),
    )


if __name__ == "__main__":
    with make_server("127.0.0.1", int(os.getenv("IAM_WORKLOAD_PORT", "5175")), application_from_env()) as server:
        server.serve_forever()
