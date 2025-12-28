from __future__ import annotations

from typing import Tuple

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest

from ..models import AppStoreApp, AppStoreLike


@transaction.atomic
def toggle_like(*, app: AppStoreApp, user) -> Tuple[bool, int]:
    """앱 좋아요를 토글하고 like_count를 갱신합니다.

    Toggle like for an app and update cached like_count.

    Returns:
        (liked, like_count)

    Side effects:
        Inserts/deletes AppStoreLike and updates AppStoreApp.like_count.
    """

    like, created = AppStoreLike.objects.select_for_update().get_or_create(app=app, user=user)
    if created:
        AppStoreApp.objects.filter(pk=app.pk).update(like_count=F("like_count") + 1)
        liked = True
    else:
        like.delete()
        AppStoreApp.objects.filter(pk=app.pk).update(like_count=Greatest(F("like_count") - 1, 0))
        liked = False

    app.refresh_from_db(fields=["like_count"])
    return liked, int(app.like_count or 0)


def increment_view_count(*, app: AppStoreApp) -> int:
    """조회수를 증가시키고 최신 값을 반환합니다.

    Increment view_count and return the new value.

    Side effects:
        Updates AppStoreApp.view_count.
    """

    AppStoreApp.objects.filter(pk=app.pk).update(view_count=F("view_count") + 1)
    app.refresh_from_db(fields=["view_count"])
    return int(app.view_count or 0)
