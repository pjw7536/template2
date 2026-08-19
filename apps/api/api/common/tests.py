# =============================================================================
# 모듈 설명: common 서비스 유틸 테스트를 제공합니다.
# - 주요 대상: normalize_text, send_knox_mail_api, Knox 메신저 어댑터
# - 불변 조건: DB 접근 없이 순수 함수 동작만 검증합니다.
# =============================================================================

from __future__ import annotations

import base64
import gzip
import json
import os
import struct
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.common.services import (
    ExternalCallCancellation,
    ExternalCallCancelled,
    ExternalHttpResponseError,
    ExternalHttpTimeout,
    MailSendError,
    api_error_response,
    ensure_airflow_token,
    normalize_text,
    parse_json_body_or_error_when_present,
    request_external,
    send_knox_mail_api,
)
from api.common.services.messenger import (
    _KnoxContext,
    _knox_testutil_compress_java_compatible,
    KnoxMessengerConfig,
    knox_decrypt,
    knox_encrypt,
    resolve_user_ids_by_single_ids,
    send_chat_message,
)
from api.common.services.middleware import (
    CanonicalApiErrorMiddleware,
    KnoxIdRequiredMiddleware,
)
from config.settings import env_json_string, env_strict_bool, env_strict_int


class StrictEnvironmentParserTests(SimpleTestCase):
    """비-Spider 설정의 엄격한 환경변수 파서를 검증합니다."""

    def test_invalid_boolean_raises_configuration_error(self) -> None:
        """알 수 없는 불리언 표기는 시작 오류로 처리합니다."""

        with patch.dict(os.environ, {"TEST_STRICT_BOOL": "sometimes"}):
            with self.assertRaises(ImproperlyConfigured):
                env_strict_bool("TEST_STRICT_BOOL")

    def test_invalid_integer_raises_configuration_error(self) -> None:
        """정수가 아닌 값은 default로 숨기지 않습니다."""

        with patch.dict(os.environ, {"TEST_STRICT_INT": "ten"}):
            with self.assertRaises(ImproperlyConfigured):
                env_strict_int("TEST_STRICT_INT", 10)

    def test_json_requires_declared_top_level_type(self) -> None:
        """JSON 설정은 구문뿐 아니라 최상위 타입도 검증합니다."""

        with patch.dict(os.environ, {"TEST_STRICT_JSON": "{}"}):
            with self.assertRaises(ImproperlyConfigured):
                env_json_string("TEST_STRICT_JSON", "[]", expected_type=list)


class CommonApiErrorContractTests(SimpleTestCase):
    """공용 요청 helper가 canonical 오류 body를 반환하는지 검증합니다."""

    def setUp(self) -> None:
        """요청 생성기를 준비합니다."""

        self.factory = RequestFactory()

    def test_error_response_has_stable_shape_for_public_statuses(self) -> None:
        """400/401/403/502/504 응답의 네 필드를 고정합니다."""

        cases = (
            (400, "invalid_request"),
            (401, "authentication_required"),
            (403, "scope_access_required"),
            (502, "external_dependency_error"),
            (504, "external_dependency_timeout"),
        )
        for status, code in cases:
            with self.subTest(status=status):
                response = api_error_response(code=code, message="공개 오류", status=status)
                self.assertEqual(response.status_code, status)
                self.assertJSONEqual(
                    response.content,
                    {
                        "code": code,
                        "message": "공개 오류",
                        "details": None,
                        "fieldErrors": {},
                    },
                )

    def test_invalid_json_object_uses_canonical_error(self) -> None:
        """잘못된 JSON object 요청을 invalid_request로 반환합니다."""

        request = self.factory.post(
            "/api/v1/test",
            data="[]",
            content_type="application/json",
        )
        payload, response = parse_json_body_or_error_when_present(request)

        self.assertEqual(payload, {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["code"], "invalid_request")

    @override_settings(AIRFLOW_TRIGGER_TOKEN="secret")
    def test_airflow_auth_failure_uses_canonical_error(self) -> None:
        """Airflow 인증 실패를 authentication_required로 반환합니다."""

        response = ensure_airflow_token(self.factory.post("/api/v1/test"))

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "authentication_required")


class CommonMiddlewareErrorContractTests(SimpleTestCase):
    """공용 middleware 오류와 Spider 제외 계약을 검증합니다."""

    def test_knox_error_is_canonical_for_non_spider_api(self) -> None:
        """비-Spider API의 Knox ID 누락 오류는 공통 형식을 사용합니다."""

        request = RequestFactory().get("/api/v1/account/overview")
        request.user = SimpleNamespace(is_authenticated=True, knox_id="")
        response = KnoxIdRequiredMiddleware(lambda current: current).process_request(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["code"], "identity_required")

    def test_spider_knox_error_keeps_legacy_contract(self) -> None:
        """제외된 Spider API의 기존 오류 body를 유지합니다."""

        request = RequestFactory().get("/api/v1/l0_spider/data")
        request.user = SimpleNamespace(is_authenticated=True, knox_id="")
        response = KnoxIdRequiredMiddleware(lambda current: current).process_request(request)

        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(response.content, {"error": "knox_id is required"})

    def test_account_legacy_error_is_canonicalized(self) -> None:
        """전환 대상 Account 오류는 공통 body와 legacy reason으로 변환합니다."""

        request = RequestFactory().post("/api/v1/account/access/request")
        original = api_error_response(
            code="invalid_request",
            message="already canonical",
            status=400,
        )
        middleware = CanonicalApiErrorMiddleware(lambda current: current)

        self.assertIs(middleware.process_response(request, original), original)

        legacy = JsonResponse({"error": "reason_required"}, status=400)
        response = middleware.process_response(request, legacy)
        self.assertJSONEqual(
            response.content,
            {
                "code": "invalid_request",
                "message": "reason_required",
                "details": {"reason": "reason_required"},
                "fieldErrors": {},
            },
        )

    def test_activity_legacy_error_is_canonicalized(self) -> None:
        """전환 대상 Activity 오류도 공통 body로 변환합니다."""

        request = RequestFactory().get("/api/v1/activity/app-access-stats")
        legacy = JsonResponse(
            {"error": "Invalid query", "details": {"period": ["invalid"]}},
            status=400,
        )

        response = CanonicalApiErrorMiddleware(lambda current: current).process_response(
            request,
            legacy,
        )

        self.assertJSONEqual(
            response.content,
            {
                "code": "invalid_request",
                "message": "Invalid query",
                "details": {"reason": "Invalid query"},
                "fieldErrors": {"period": ["invalid"]},
            },
        )

    def test_canonicalized_error_preserves_transport_metadata(self) -> None:
        """오류 body 변환 후에도 원본 HTTP header와 cookie를 유지합니다."""

        request = RequestFactory().get("/api/v1/voc/posts")
        legacy = JsonResponse({"error": "retry later"}, status=429)
        legacy["Allow"] = "GET, POST"
        legacy["Retry-After"] = "60"
        legacy["Content-Length"] = "999"
        legacy.set_cookie("retry_hint", "1", httponly=True, samesite="Lax")

        response = CanonicalApiErrorMiddleware(lambda current: current).process_response(
            request,
            legacy,
        )

        self.assertEqual(response["Allow"], "GET, POST")
        self.assertEqual(response["Retry-After"], "60")
        self.assertNotEqual(response.get("Content-Length"), "999")
        self.assertEqual(response.cookies["retry_hint"].value, "1")
        self.assertTrue(response.cookies["retry_hint"]["httponly"])
        self.assertEqual(response.cookies["retry_hint"]["samesite"], "Lax")


class ExternalHttpAdapterTests(SimpleTestCase):
    """공용 외부 HTTP adapter의 timeout과 취소 분류를 검증합니다."""

    def test_connect_and_read_timeout_are_distinguished(self) -> None:
        """연결/응답 timeout 단계를 각각 보존합니다."""

        for exception, phase in (
            (requests.ConnectTimeout(), "connect"),
            (requests.ReadTimeout(), "read"),
        ):
            requester = Mock(side_effect=exception)
            with self.subTest(phase=phase), self.assertRaises(ExternalHttpTimeout) as ctx:
                request_external(requester, "https://example.test", timeout=(1, 2))
            self.assertEqual(ctx.exception.phase, phase)

    def test_http_error_preserves_status_without_body(self) -> None:
        """외부 HTTP 실패는 상태 코드만 안전하게 보존합니다."""

        response = Mock(status_code=502)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        with self.assertRaises(ExternalHttpResponseError) as ctx:
            request_external(
                Mock(return_value=response),
                "https://example.test",
                timeout=1,
                raise_for_status=True,
            )
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertNotIn("response", str(ctx.exception).lower())

    def test_cancelled_request_does_not_call_transport(self) -> None:
        """이미 취소된 호출은 network 요청 전에 중단합니다."""

        cancellation = ExternalCallCancellation()
        cancellation.cancel()
        requester = Mock()
        with self.assertRaises(ExternalCallCancelled):
            request_external(
                requester,
                "https://example.test",
                timeout=1,
                cancellation=cancellation,
            )
        requester.assert_not_called()

    def test_disconnect_wins_over_transport_timeout(self) -> None:
        """동시 취소된 요청은 timeout 응답이 아니라 취소로 분류합니다."""

        cancellation = ExternalCallCancellation()

        def cancel_then_timeout(*args: object, **kwargs: object) -> None:
            cancellation.cancel()
            raise requests.ReadTimeout()

        with self.assertRaises(ExternalCallCancelled):
            request_external(
                cancel_then_timeout,
                "https://example.test",
                timeout=1,
                cancellation=cancellation,
            )


class CommonNormalizationTests(SimpleTestCase):
    """공용 정규화 유틸 동작을 검증합니다."""

    def test_normalize_text_trims_text(self) -> None:
        """문자열 입력의 앞뒤 공백이 제거되는지 확인합니다."""

        self.assertEqual(normalize_text("  hello  "), "hello")

    def test_normalize_text_returns_empty_for_non_string(self) -> None:
        """문자열이 아니면 빈 문자열을 반환하는지 확인합니다."""

        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(123), "")


class KnoxMailApiTests(SimpleTestCase):
    """공용 Knox 메일 발송 어댑터 동작을 검증합니다."""

    @override_settings(
        MAIL_API_URL="http://mail.test/send",
        MAIL_API_KEY="ticket",
        MAIL_API_SYSTEM_ID="plane",
        MAIL_API_KNOX_ID="knox-user",
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_returns_json(self, mock_post: Mock) -> None:
        """JSON 응답이 dict로 반환되는지 확인합니다."""

        response = Mock()
        response.ok = True
        response.status_code = 200
        response.text = ""
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"status": "ok"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com", "b@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"status": "ok"})
        mock_post.assert_called_once_with(
            "http://mail.test/send",
            params={"systemId": "plane", "loginUser.login": "knox-user"},
            headers={"x-dep-ticket": "ticket"},
            json={
                "receiverList": [
                    {"email": "a@example.com", "recipientType": "TO"},
                    {"email": "b@example.com", "recipientType": "TO"},
                ],
                "title": "Subject",
                "content": "<p>Hello</p>",
                "senderMailAddress": "sender@example.com",
            },
            timeout=10,
        )

    @override_settings(
        MAIL_API_URL="http://mail.test/send",
        MAIL_API_KEY="ticket",
        MAIL_API_SYSTEM_ID="plane",
        MAIL_API_KNOX_ID="knox-user",
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_returns_ok_for_non_json(self, mock_post: Mock) -> None:
        """비 JSON 응답은 ok=True로 처리되는지 확인합니다."""

        response = Mock()
        response.ok = True
        response.status_code = 204
        response.text = ""
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"ok": True})

    @override_settings(
        MAIL_API_URL="http://mail.test/send",
        MAIL_API_KEY="ticket",
        MAIL_API_SYSTEM_ID="plane",
        MAIL_API_KNOX_ID="knox-user",
    )
    @patch("api.common.services.mail_api.requests.post")
    def test_send_knox_mail_api_raises_on_http_error(self, mock_post: Mock) -> None:
        """HTTP 오류 응답 시 예외가 발생하는지 확인합니다."""

        response = Mock()
        response.ok = False
        response.status_code = 500
        response.text = "server error"
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        with self.assertRaises(MailSendError) as ctx:
            send_knox_mail_api(
                sender_email="sender@example.com",
                receiver_emails=["a@example.com"],
                subject="Subject",
                html_content="<p>Hello</p>",
            )
        self.assertIn("메일 API 오류 500", str(ctx.exception))

    def test_send_knox_mail_api_raises_when_missing_settings(self) -> None:
        """Django 설정 누락 시 예외가 발생하는지 확인합니다."""

        with override_settings(
            MAIL_API_URL="",
            MAIL_API_KEY="",
            MAIL_API_SYSTEM_ID="",
            MAIL_API_KNOX_ID="",
        ):
            with self.assertRaises(MailSendError):
                send_knox_mail_api(
                    sender_email="sender@example.com",
                    receiver_emails=["a@example.com"],
                    subject="Subject",
                    html_content="<p>Hello</p>",
                )


class KnoxMessengerClientUtilsTests(SimpleTestCase):
    """Knox 메신저 유틸 함수 단위 테스트."""

    @override_settings(
        KNOX_MESSENGER_API_BASE_URL="https://messenger.test/api/",
        KNOX_MESSENGER_AUTHORIZATION="Bearer test-token",
        KNOX_MESSENGER_SYSTEM_ID="portal",
        KNOX_MESSENGER_TIMEOUT_SECONDS=17,
    )
    def test_config_reads_canonical_django_settings(self) -> None:
        """Knox 설정은 runtime 환경변수 대신 Django settings만 읽습니다."""

        config = KnoxMessengerConfig.from_settings()

        self.assertEqual(config.base_url, "https://messenger.test/api/")
        self.assertEqual(config.authorization, "Bearer test-token")
        self.assertEqual(config.system_id, "portal")
        self.assertEqual(config.timeout_seconds, 17)

    def test_knox_encrypt_decrypt_roundtrip(self) -> None:
        """AES-CBC 암복호화 라운드트립을 검증합니다."""

        key = bytes.fromhex(
            "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
        )
        iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
        plaintext = "테스트 메시지"

        ciphertext = knox_encrypt(key, iv, plaintext)
        decrypted = knox_decrypt(key, iv, ciphertext)

        self.assertEqual(decrypted, plaintext)

    def test_knox_testutil_compress_java_compatible(self) -> None:
        """Java TestUtil.compress() 호환 압축 결과를 검증합니다."""

        value = "ABC가나다123"
        encoded = _knox_testutil_compress_java_compatible(value)
        raw = base64.b64decode(encoded)

        header = raw[:4]
        gzipped = raw[4:]
        header_value = struct.unpack("<I", header)[0]
        self.assertEqual(header_value, int(len(value) * 1.2))

        restored = gzip.decompress(gzipped).decode("utf-8")
        self.assertEqual(restored, value)

    def test_send_chat_message_sends_given_msg_type_and_string(self) -> None:
        """send_chat_message가 전달받은 msg_type과 문자열 본문을 전송하는지 확인합니다."""

        dummy_context = _KnoxContext(
            base_url="http://example.local/",
            headers={},
            key=b"0" * 32,
            iv=b"1" * 16,
            timeout_seconds=1,
        )
        captured: dict[str, object] = {}

        def _capture_payload(context: _KnoxContext, path: str, payload: dict[str, object]) -> object:
            captured["path"] = path
            captured["payload"] = payload
            return object()

        with patch(
            "api.common.services.messenger._prepare_knox_context",
            return_value=dummy_context,
        ), patch(
            "api.common.services.messenger._post_encrypted",
            side_effect=_capture_payload,
        ):
            send_chat_message(chatroom_id=1, msg_type=7, chat_msg="{\"a\": 1}")

        payload = captured.get("payload")
        self.assertIsInstance(payload, dict)
        params = payload["chatMessageParams"][0]
        self.assertEqual(params["msgType"], 7)
        self.assertEqual(params["chatMsg"], "{\"a\": 1}")

    def test_resolve_user_ids_by_single_ids_casts_user_id_to_string(self) -> None:
        """singleID 조회 결과의 userID가 숫자여도 문자열로 반환하는지 확인합니다."""

        mocked_results = [
            {"singleID": "abc.park", "userID": 123123123123},
            {"singleID": "def.park", "userID": "U-2"},
        ]

        with patch(
            "api.common.services.messenger.search_user_ids_by_single_ids",
            return_value=mocked_results,
        ):
            resolved = resolve_user_ids_by_single_ids(single_ids=["abc.park", "def.park"])

        self.assertEqual(resolved, ["123123123123", "U-2"])
