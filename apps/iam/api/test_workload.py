"""월별 업무 부하 저장의 검증과 동시 수정 방지를 확인합니다."""

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from workload import METRICS, RequestError, create_app, keycloak_authorizer


def check_token(authorization):
    if authorization != "Bearer test":
        raise RequestError("401 Unauthorized", "IAM 로그인이 필요합니다.")


class WorkloadTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "workload.sqlite3"
        self.app = create_app(self.database, check_token)
        self.payload = {
            "revision": 0,
            "weights": dict.fromkeys(METRICS, 1),
            "records": [{
                "teamId": "team-a", "team": "A팀", "lineId": "line-1", "line": "1라인",
                "headcount": 12, "difficulty": "높음", "averageHours": 181.5, "sciScore": 83.25, "notes": "야간 대응",
                "totalClicks": 12001, "totalWfMoves": 350020,
                **dict.fromkeys(METRICS, 0),
            }],
        }

    def request(self, method="GET", month="2026-11", payload=None, token="Bearer test"):
        environ = {}
        setup_testing_defaults(environ)
        body = json.dumps(payload).encode()
        environ.update({
            "REQUEST_METHOD": method, "PATH_INFO": f"/api/workload/{month}",
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body), "HTTP_AUTHORIZATION": token,
        })
        statuses = []
        response = self.app(environ, lambda status, _headers: statuses.append(status))
        return int(statuses[0].split()[0]), json.loads(b"".join(response))

    def test_reopens_database_and_keeps_months_separate(self):
        status, saved = self.request("PUT", payload=self.payload)
        self.assertEqual(status, 200)
        self.assertEqual(saved, self.payload | {"revision": 1})
        self.app = create_app(self.database, check_token)
        self.assertEqual(self.request(), (200, saved))
        self.assertEqual(self.request(month="2026-10"), (200, {"revision": 0, "records": []}))

    def test_conflict_does_not_replace_the_saved_month(self):
        self.assertEqual(self.request("PUT", payload=self.payload)[0], 200)
        self.assertEqual(self.request("PUT", payload=self.payload)[0], 409)
        status, saved = self.request("PUT", payload=self.payload | {"revision": 1, "records": []})
        self.assertEqual((status, saved["revision"]), (200, 2))
        self.assertEqual(self.request("PUT", payload=self.payload | {"revision": 1})[0], 409)
        self.assertEqual(self.request()[1]["records"], [])

    def test_rejects_invalid_input_and_unauthorized_requests(self):
        self.assertEqual(self.request(token="")[0], 401)
        self.assertEqual(self.request("PUT", payload=self.payload, token="")[0], 401)
        self.assertEqual(self.request(month="2026-13")[0], 404)
        self.payload["records"][0]["fdc"] = -1
        self.assertEqual(self.request("PUT", payload=self.payload)[0], 400)
        self.assertEqual(self.request()[1]["records"], [])

    def test_checks_signature_client_and_management_role(self):
        issuer = "https://keycloak.example/realms/test"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        claims = {
            "iss": issuer, "sub": "admin", "aud": "realm-management", "azp": "iam", "typ": "Bearer",
            "iat": now, "exp": now + timedelta(minutes=5),
            "resource_access": {"realm-management": {"roles": ["manage-users"]}},
        }
        with patch.object(jwt.PyJWKClient, "get_signing_key_from_jwt", return_value=SimpleNamespace(key=key.public_key())):
            authorize = keycloak_authorizer(issuer, "iam")
            authorize("Bearer " + jwt.encode(claims, key, algorithm="RS256"))
            for overrides in ({"azp": "portal"}, {"resource_access": {}}, {"typ": "Refresh"}):
                with self.subTest(overrides=overrides), self.assertRaises(RequestError) as denied:
                    authorize("Bearer " + jwt.encode(claims | overrides, key, algorithm="RS256"))
                self.assertEqual(denied.exception.status, "403 Forbidden")
            with self.assertRaises(RequestError) as invalid:
                authorize("Bearer " + jwt.encode(claims, "x" * 32, algorithm="HS256"))
            self.assertEqual(invalid.exception.status, "401 Unauthorized")

    def test_sci_distinguishes_zero_from_missing_and_rejects_invalid_scores(self):
        record = self.payload["records"][0]
        record.pop("sciScore")
        status, saved = self.request("PUT", payload=self.payload)
        self.assertEqual(status, 200)
        self.assertIsNone(saved["records"][0]["sciScore"])

        self.payload["revision"] = 1
        for value in (-1, "85", True, float("inf")):
            with self.subTest(value=value):
                record["sciScore"] = value
                self.assertEqual(self.request("PUT", payload=self.payload)[0], 400)

        record["sciScore"] = 0
        self.assertEqual(self.request("PUT", payload=self.payload)[0], 200)
        self.assertEqual(self.request()[1]["records"][0]["sciScore"], 0)

    def test_monthly_totals_keep_legacy_average_separate_and_distinguish_zero_from_missing(self):
        record = self.payload["records"][0]
        record.pop("totalClicks")
        record.pop("totalWfMoves")
        record["clicksPerPerson"] = 1200.5
        status, saved = self.request("PUT", payload=self.payload)
        self.assertEqual(status, 200)
        self.assertIsNone(saved["records"][0]["totalClicks"])
        self.assertIsNone(saved["records"][0]["totalWfMoves"])
        self.assertEqual(saved["records"][0]["clicksPerPerson"], 1200.5)

        self.payload["revision"] = 1
        for key in ("totalClicks", "totalWfMoves"):
            for value in (-1, 1.5):
                with self.subTest(key=key, value=value):
                    record[key] = value
                    self.assertEqual(self.request("PUT", payload=self.payload)[0], 400)
            record[key] = 0
        self.assertEqual(self.request("PUT", payload=self.payload)[0], 200)
        saved_record = self.request()[1]["records"][0]
        self.assertEqual(saved_record["totalClicks"], 0)
        self.assertEqual(saved_record["totalWfMoves"], 0)
        self.assertEqual(saved_record["clicksPerPerson"], 1200.5)


if __name__ == "__main__":
    unittest.main()
