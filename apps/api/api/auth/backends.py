from __future__ import annotations  # 타입 힌트의 전방 참조를 안정적으로 사용하기 위함

import os
from typing import Any, Dict

from django.conf import settings  # Django 설정 접근
from django.contrib.auth import get_user_model  # 현재 프로젝트의 사용자 모델 참조 함수
from mozilla_django_oidc.auth import OIDCAuthenticationBackend  # OIDC 기본 백엔드

from ..models import ensure_user_profile  # 유저 프로필 생성/보장 유틸(프로젝트별 구현)


class RPAuthenticationBackend(OIDCAuthenticationBackend):
    """
    OIDC 인증 백엔드 (RP = Relying Party)
    - 평소에는 OIDC로 사용자 인증을 처리
    - 개발 모드(dev) + OIDC 미구성일 때는 환경변수 기반 더미 계정으로 로그인 허용
    """

    @staticmethod
    def _is_oidc_configured() -> bool:
        """
        OIDC 필수 설정(클라이언트 ID, 인증 엔드포인트)이 있는지 확인.
        - 둘 중 하나라도 없으면 OIDC 미구성으로 판단.
        """
        return bool(
            getattr(settings, "OIDC_RP_CLIENT_ID", None)
            and getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", None)
        )

    @staticmethod
    def _is_dev_login_enabled() -> bool:
        """
        개발용 로그인 허용 플래그 확인.
        - settings.OIDC_DEV_LOGIN_ENABLED 가 True 면 개발 로그인 허용.
        """
        return bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))

    def filter_users_by_claims(self, claims: Dict[str, Any]):
        """
        OIDC 클레임(토큰 정보)으로 사용자 후보를 필터링.
        - 이메일이 없으면 검색 불가 → 빈 쿼리셋 반환.
        - 이메일이 있으면 대소문자 무시(iexact)로 매칭.
        """
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def create_user(self, claims: Dict[str, Any]):
        """
        OIDC 클레임으로 새 사용자 생성 후, update_user 로 세부 정보 갱신.
        - super().create_user 가 기본 유저를 만든 뒤,
        - 추가 필드(이름, 성 등)를 정리하려고 update_user 호출.
        """
        user = super().create_user(claims)
        return self.update_user(user, claims)

    def update_user(self, user, claims: Dict[str, Any]):
        """
        OIDC 클레임을 바탕으로 사용자 필드를 업데이트.
        - email, name(전체 이름)에서 first_name/last_name 추출 저장.
        - ensure_user_profile 로 사용자 프로필 존재 보장.
        """
        user.email = claims.get("email") or user.email
        full_name = claims.get("name") or ""
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                # 최소 "이름 성" 형태면 첫 단어를 first_name, 나머지를 last_name 으로
                user.first_name = parts[0]
                user.last_name = " ".join(parts[1:])
            else:
                # 단어가 하나뿐이면 first_name 에만 저장
                user.first_name = full_name
        user.save()
        ensure_user_profile(user)  # 사용자 프로필 생성/업데이트 보장 (프로젝트별 유틸)
        return user

    def authenticate(self, request, **kwargs):
        """
        핵심 인증 로직.
        - (A) 개발 로그인 허용 + OIDC 미구성 → 환경변수로 더미 계정 자동 로그인
        - (B) 그 외에는 OIDC 기본 인증(super) 수행
        """
        if self._is_dev_login_enabled() and not self._is_oidc_configured():
            # 🔹 개발 모드 더미 계정 정보 (없으면 기본값 사용)
            dummy_email = os.environ.get("AUTH_DUMMY_EMAIL", "demo@example.com")
            dummy_name = os.environ.get("AUTH_DUMMY_NAME", "Demo User")

            user_model = get_user_model()
            # username 기본값은 이메일의 @ 앞부분 (이메일 형식 아닐 수도 있으니 방어)
            username = dummy_email.split("@")[0] if "@" in dummy_email else dummy_email

            # 이메일 기준으로 유저 조회/생성
            user, created = user_model.objects.get_or_create(
                email=dummy_email,
                defaults={"username": username or "dev-user", "first_name": dummy_name},
            )
            if created:
                # 비밀번호 미사용 계정(외부 인증만 허용)으로 마킹
                user.set_unusable_password()
                user.save()

            ensure_user_profile(user)  # 프로필 보장
            return user  # ✅ 개발 모드에서는 여기서 곧바로 인증 성공 반환

        # 🔹 일반 모드: OIDC 표준 인증 절차 진행
        return super().authenticate(request, **kwargs)

    def get_settings(self, attr, default=None):
        """
        상위 클래스에서 참조하는 설정 가져오기 헬퍼.
        - getattr 로 settings 에서 안전하게 읽어온다.
        """
        return getattr(settings, attr, default)

    def verify_claims(self, claims: Dict[str, Any]):
        """
        OIDC 제공자 측에서 받은 클레임 검증 단계.
        - 개발 로그인 허용 + OIDC 미구성인 경우에는 검증을 우회(그대로 통과).
        - 그 외에는 상위(super) 검증 로직 사용.
        """
        if self._is_dev_login_enabled() and not self._is_oidc_configured():
            return claims  # 검증 우회 (dev 전용)
        return super().verify_claims(claims)

    def user_can_authenticate(self, user):
        """
        최종적으로 이 사용자가 로그인 가능 상태인지 확인.
        - 비활성화된 유저(is_active=False)는 차단.
        - 나머지는 기본(상위) 정책에 따름.
        """
        if not user.is_active:
            return False
        return super().user_can_authenticate(user)
