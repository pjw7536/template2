# =============================================================================
# 모듈 설명: 로컬 개발용 Appstore 앱 더미 데이터를 생성합니다.
# - 주요 함수: seed_appstore_dummy_data
# - 불변 조건: `[PREFIX] ` 이름 marker가 붙은 앱만 조회·갱신·삭제합니다.
# =============================================================================

from __future__ import annotations

from typing import Any

from ..selectors import get_seeded_apps
from .apps import create_app, delete_app, update_app


APPSTORE_DUMMY_SPECS = (
    {
        "name": "설비 상태 모니터",
        "category": "DX App",
        "description": "설비 상태와 주요 알람을 한 화면에서 확인하는 개발용 샘플 앱입니다.",
        "url": "https://example.com/appstore/equipment-monitor",
    },
    {
        "name": "엔지니어 업무 도우미",
        "category": "Engineer App",
        "description": "교대 업무와 점검 항목을 정리하는 개발용 샘플 앱입니다.",
        "url": "https://example.com/appstore/engineer-helper",
    },
    {
        "name": "Etch 일일 리포트",
        "category": "Etch Report",
        "description": "Etch 주요 지표와 이상 항목을 요약한 개발용 샘플 리포트입니다.",
        "url": "https://example.com/appstore/etch-daily-report",
    },
    {
        "name": "PM 일정 리포트",
        "category": "PM Report",
        "description": "예방 정비 일정과 진행 상태를 확인하는 개발용 샘플 리포트입니다.",
        "url": "https://example.com/appstore/pm-schedule-report",
    },
    {
        "name": "품질 추이 대시보드",
        "category": "품질 Report",
        "description": "품질 지표의 일별 추이를 비교하는 개발용 샘플 대시보드입니다.",
        "url": "https://example.com/appstore/quality-trend",
    },
    {
        "name": "환경안전 점검표",
        "category": "환경안전 Report",
        "description": "환경안전 점검 결과와 조치 상태를 확인하는 개발용 샘플입니다.",
        "url": "https://example.com/appstore/safety-check",
    },
    {
        "name": "생산 지원 현황",
        "category": "생산지원 Report",
        "description": "생산 지원 요청과 처리 현황을 보여주는 개발용 샘플입니다.",
        "url": "https://example.com/appstore/production-support",
    },
    {
        "name": "E린이 시작 가이드",
        "category": "E린이 필수 App",
        "description": "신규 사용자가 주요 업무 도구를 익히기 위한 개발용 샘플 가이드입니다.",
        "url": "https://example.com/appstore/beginner-guide",
    },
)


def seed_appstore_dummy_data(
    *,
    prefix: str,
    owner: Any,
    reset: bool = False,
) -> dict[str, int]:
    """Appstore 순서 관리 확인용 더미 앱을 결정적으로 생성하거나 갱신합니다.

    인자:
        prefix: seed 앱 이름을 실제 앱과 구분할 영문 prefix.
        owner: seed 앱 소유자로 지정할 dev dummy 사용자.
        reset: True이면 같은 marker의 기존 seed 앱을 먼저 삭제합니다.

    반환:
        삭제, 생성, 갱신, 전체 샘플 개수를 담은 dict.

    부작용:
        AppStoreApp seed 레코드를 생성, 갱신 또는 삭제합니다.

    오류:
        prefix가 비어 있으면 ValueError를 발생시키며 ORM 오류는 호출자에게 전파합니다.
    """

    normalized_prefix = str(prefix or "").strip().upper()
    if not normalized_prefix:
        raise ValueError("prefix must not be empty")

    name_prefix = f"[{normalized_prefix}] "
    seeded_apps = list(get_seeded_apps(name_prefix=name_prefix))
    deleted = 0
    if reset:
        for app in seeded_apps:
            delete_app(app=app)
            deleted += 1
        seeded_apps = []

    apps_by_name = {app.name: app for app in seeded_apps}
    contact_name = str(getattr(owner, "username", "") or "Dummy User")
    contact_knoxid = str(getattr(owner, "knox_id", "") or "dummy.user")
    created = 0
    updated = 0

    # -----------------------------------------------------------------------------
    # 고정된 sample 순서대로 생성해 최초 display_order도 재현 가능하게 유지합니다.
    # -----------------------------------------------------------------------------
    for spec in APPSTORE_DUMMY_SPECS:
        name = f"{name_prefix}{spec['name']}"
        existing = apps_by_name.get(name)
        common_values = {
            "name": name,
            "category": spec["category"],
            "description": spec["description"],
            "url": spec["url"],
            "manual_url": None,
            "screenshot_urls": [],
            "contact_name": contact_name,
            "contact_knoxid": contact_knoxid,
            "owner": owner,
        }
        if existing is None:
            create_app(
                owner=owner,
                name=name,
                category=str(spec["category"]),
                description=str(spec["description"]),
                url=str(spec["url"]),
                manual_url=None,
                screenshot_urls=[],
                screenshot_url="",
                contact_name=contact_name,
                contact_knoxid=contact_knoxid,
            )
            created += 1
            continue

        update_app(app=existing, updates=dict(common_values))
        updated += 1

    return {
        "deleted": deleted,
        "created": created,
        "updated": updated,
        "total": len(APPSTORE_DUMMY_SPECS),
    }
