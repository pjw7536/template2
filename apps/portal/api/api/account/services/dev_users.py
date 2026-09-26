"""명시적인 로컬 seed용 일반 사용자를 준비합니다. 권한은 Keycloak 로그인에서만 받습니다."""
from __future__ import annotations
import os
from .identity import upsert_user_identity


def ensure_dev_dummy_user():
    """개발 seed 소유자를 EPID로 생성하며 비밀번호·staff·업무 권한을 부여하지 않습니다."""
    if os.environ.get("ENVIRONMENT") != "development":
        return None
    user, _ = upsert_user_identity(identity={"avatarid": "90000001", "username": "dummy.user",
        "email": "dummy.user@example.com", "department": "Local Etch", "deptid": "LOCAL-ETCH",
        "identity_profile": {"user_sdwt_prod": "SDWT-A", "line_id": "LINE-1"}},
        sabun="S000001", knox_id="dummy.user")
    return user
