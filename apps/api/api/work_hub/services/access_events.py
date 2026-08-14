"""Portal account 변경을 Grist 접근 권한 Outbox에 연결합니다."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

from api.account import selectors as account_selectors

from .access import (
    enqueue_access_sync_for_affiliations,
    enqueue_access_sync_for_all_affiliations,
)


ACCESS_AFFECTING_SCOPE_KEYS = {"portal", "work-hub"}


def _enabled() -> bool:
    """Work Hub가 활성화된 환경에서만 변경 이벤트를 적재합니다."""

    return bool(getattr(settings, "WORK_HUB_ENABLED", False))


def _enqueue(*, affiliation_ids: set[int], reason: str) -> None:
    """유효한 소속 ID가 있을 때 동일 트랜잭션에 Outbox를 적재합니다."""

    if not _enabled() or not affiliation_ids:
        return
    enqueue_access_sync_for_affiliations(
        affiliation_ids=affiliation_ids,
        reason=reason,
    )


def _enqueue_all(*, reason: str) -> None:
    """접근 정책이 여러 소속 사용자에게 영향을 줄 때 전체를 재동기화합니다."""

    if not _enabled():
        return
    enqueue_access_sync_for_all_affiliations(reason=reason)


def _capture_current_affiliation_before_save(
    sender: Any, instance: Any, **kwargs: Any
) -> None:
    """현재 소속 변경 전 소속 ID를 instance에 임시 보관합니다."""

    previous = None
    if getattr(instance, "pk", None):
        previous = account_selectors.get_current_affiliation_id_by_record_id(
            record_id=instance.pk
        )
    instance._grist_previous_affiliation_id = previous


def _current_affiliation_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """이전·신규 소속 Space를 함께 재동기화합니다."""

    affiliation_ids = {
        value
        for value in (
            getattr(instance, "_grist_previous_affiliation_id", None),
            getattr(instance, "affiliation_id", None),
        )
        if isinstance(value, int)
    }
    _enqueue(affiliation_ids=affiliation_ids, reason="current_affiliation_changed")


def _current_affiliation_deleted(sender: Any, instance: Any, **kwargs: Any) -> None:
    """현재 소속 삭제 시 기존 Space에서 사용자를 회수합니다."""

    affiliation_id = getattr(instance, "affiliation_id", None)
    _enqueue(
        affiliation_ids={affiliation_id} if isinstance(affiliation_id, int) else set(),
        reason="current_affiliation_deleted",
    )


def _capture_access_before_save(sender: Any, instance: Any, **kwargs: Any) -> None:
    """명시 소속 권한 변경 전 소속 ID를 instance에 임시 보관합니다."""

    previous = None
    if getattr(instance, "pk", None):
        previous = account_selectors.get_access_affiliation_id_by_record_id(
            record_id=instance.pk
        )
    instance._grist_previous_affiliation_id = previous


def _access_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """명시 소속 권한 생성·역할 변경·소속 이동을 재동기화합니다."""

    affiliation_ids = {
        value
        for value in (
            getattr(instance, "_grist_previous_affiliation_id", None),
            getattr(instance, "affiliation_id", None),
        )
        if isinstance(value, int)
    }
    _enqueue(affiliation_ids=affiliation_ids, reason="affiliation_access_changed")


def _access_deleted(sender: Any, instance: Any, **kwargs: Any) -> None:
    """명시 소속 권한 삭제 시 기존 Space에서 사용자를 회수합니다."""

    affiliation_id = getattr(instance, "affiliation_id", None)
    _enqueue(
        affiliation_ids={affiliation_id} if isinstance(affiliation_id, int) else set(),
        reason="affiliation_access_deleted",
    )


def _capture_user_before_save(sender: Any, instance: Any, **kwargs: Any) -> None:
    """이메일·활성·superuser 상태 변경 전 접근 동기화 상태를 보관합니다."""

    state = None
    if getattr(instance, "pk", None):
        state = account_selectors.get_user_access_sync_state(user_id=instance.pk)
    instance._grist_previous_access_state = state


def _user_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """사용자 identity나 superuser 상태가 바뀐 document를 재동기화합니다."""

    previous = getattr(instance, "_grist_previous_access_state", None)
    current_superuser = bool(getattr(instance, "is_superuser", False))
    if not previous:
        if current_superuser:
            _enqueue_all(reason="user_identity_changed")
        return
    current_email = str(getattr(instance, "email", "") or "").strip().lower()
    current_active = bool(getattr(instance, "is_active", False))
    current_department = str(getattr(instance, "department", "") or "").strip()
    if (
        previous["email"] == current_email
        and previous["is_active"] == current_active
        and previous["is_superuser"] == current_superuser
        and previous["department"] == current_department
    ):
        return
    if previous["is_superuser"] or current_superuser:
        _enqueue_all(reason="user_identity_changed")
        return
    current_ids = account_selectors.list_affiliation_ids_for_user_id(
        user_id=instance.pk
    )
    _enqueue(
        affiliation_ids=set(previous["affiliation_ids"]) | current_ids,
        reason="user_identity_changed",
    )


def _capture_user_before_delete(sender: Any, instance: Any, **kwargs: Any) -> None:
    """사용자 cascade 삭제 전에 영향받는 소속 ID를 보관합니다."""

    instance._grist_deleted_was_superuser = bool(
        getattr(instance, "is_superuser", False)
    )
    instance._grist_deleted_affiliation_ids = (
        account_selectors.list_affiliation_ids_for_user_id(user_id=instance.pk)
    )


def _user_deleted(sender: Any, instance: Any, **kwargs: Any) -> None:
    """삭제된 사용자를 기존 소속 Space에서 회수합니다."""

    if getattr(instance, "_grist_deleted_was_superuser", False):
        _enqueue_all(reason="user_deleted")
        return
    _enqueue(
        affiliation_ids=set(
            getattr(instance, "_grist_deleted_affiliation_ids", set())
        ),
        reason="user_deleted",
    )


def _affiliation_saved(sender: Any, instance: Any, **kwargs: Any) -> None:
    """소속 부서·활성 상태가 정책 판정에 미치는 영향을 전체에 반영합니다."""

    _enqueue_all(reason="affiliation_changed")


def _capture_user_access_before_change(
    sender: Any, instance: Any, **kwargs: Any
) -> None:
    """UserAccess 변경 전 사용자와 scope를 instance에 보관합니다."""

    state = None
    if getattr(instance, "pk", None):
        state = account_selectors.get_user_access_signal_state(record_id=instance.pk)
    instance._grist_previous_user_access_state = state


def _user_access_changed(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Portal 또는 Work Hub 최종 권한 변경을 모든 document에 반영합니다."""

    previous = getattr(instance, "_grist_previous_user_access_state", None) or {}
    current_scope_key = account_selectors.get_access_scope_key_by_id(
        scope_id=getattr(instance, "scope_id", 0)
    )
    scope_keys = {previous.get("scope_key"), current_scope_key}
    if not scope_keys.intersection(ACCESS_AFFECTING_SCOPE_KEYS):
        return
    # `data_scope_mode=all`과 Portal 접근 회수는 기존 소속 행만으로 영향 범위를
    # 좁힐 수 없으므로 모든 Work Hub mapping을 desired state로 재계산합니다.
    _enqueue_all(reason="app_access_changed")


def _capture_scope_affiliation_grant_before_change(
    sender: Any, instance: Any, **kwargs: Any
) -> None:
    """앱별 소속 grant 변경 전 scope와 소속 ID를 보관합니다."""

    state = None
    if getattr(instance, "pk", None):
        state = account_selectors.get_scope_affiliation_grant_signal_state(
            record_id=instance.pk
        )
    instance._grist_previous_scope_affiliation_grant_state = state


def _scope_affiliation_grant_changed(
    sender: Any, instance: Any, **kwargs: Any
) -> None:
    """Work Hub 앱별 grant 생성·변경·삭제를 해당 document에 반영합니다."""

    previous = getattr(
        instance,
        "_grist_previous_scope_affiliation_grant_state",
        None,
    ) or {}
    current_scope_key = account_selectors.get_access_scope_key_by_id(
        scope_id=getattr(instance, "scope_id", 0)
    )
    scope_keys = {previous.get("scope_key"), current_scope_key}
    if "work-hub" not in scope_keys:
        return
    affiliation_ids = {
        value
        for value in (
            previous.get("affiliation_id"),
            getattr(instance, "affiliation_id", None),
        )
        if isinstance(value, int)
    }
    _enqueue(
        affiliation_ids=affiliation_ids,
        reason="scope_affiliation_grant_changed",
    )


def _capture_policy_before_change(
    sender: Any, instance: Any, **kwargs: Any
) -> None:
    """접근 정책 변경 전 scope key를 instance에 보관합니다."""

    scope_key = None
    if getattr(instance, "pk", None):
        scope_key = account_selectors.get_access_policy_scope_key_by_record_id(
            record_id=instance.pk
        )
    instance._grist_previous_policy_scope_key = scope_key


def _access_policy_changed(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Portal 또는 Work Hub 부서 정책 변경 시 전체 document를 재동기화합니다."""

    current_scope_key = account_selectors.get_access_scope_key_by_id(
        scope_id=getattr(instance, "scope_id", 0)
    )
    scope_keys = {
        getattr(instance, "_grist_previous_policy_scope_key", None),
        current_scope_key,
    }
    if scope_keys.intersection(ACCESS_AFFECTING_SCOPE_KEYS):
        _enqueue_all(reason="app_access_policy_changed")


def _capture_scope_before_change(sender: Any, instance: Any, **kwargs: Any) -> None:
    """접근 scope key 변경 전 값을 instance에 보관합니다."""

    previous_key = None
    if getattr(instance, "pk", None):
        previous_key = account_selectors.get_access_scope_key_by_id(
            scope_id=instance.pk
        )
    instance._grist_previous_scope_key = previous_key


def _access_scope_changed(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Portal 또는 Work Hub scope 계약 변경 시 전체 document를 재동기화합니다."""

    scope_keys = {
        getattr(instance, "_grist_previous_scope_key", None),
        str(getattr(instance, "key", "") or ""),
    }
    if scope_keys.intersection(ACCESS_AFFECTING_SCOPE_KEYS):
        _enqueue_all(reason="app_access_scope_changed")


def register_access_sync_signals(
    *,
    user_model: Any,
    affiliation_model: Any,
    current_affiliation_model: Any,
    access_model: Any,
    user_access_model: Any,
    scope_affiliation_grant_model: Any,
    access_policy_model: Any,
    access_scope_model: Any,
) -> None:
    """account 모델 신호를 중복 없이 Work Hub Outbox handler에 연결합니다."""

    pre_save.connect(
        _capture_current_affiliation_before_save,
        sender=current_affiliation_model,
        weak=False,
        dispatch_uid="work_hub.current_affiliation.pre_save",
    )
    post_save.connect(
        _current_affiliation_saved,
        sender=current_affiliation_model,
        weak=False,
        dispatch_uid="work_hub.current_affiliation.post_save",
    )
    post_delete.connect(
        _current_affiliation_deleted,
        sender=current_affiliation_model,
        weak=False,
        dispatch_uid="work_hub.current_affiliation.post_delete",
    )
    pre_save.connect(
        _capture_access_before_save,
        sender=access_model,
        weak=False,
        dispatch_uid="work_hub.affiliation_access.pre_save",
    )
    post_save.connect(
        _access_saved,
        sender=access_model,
        weak=False,
        dispatch_uid="work_hub.affiliation_access.post_save",
    )
    post_delete.connect(
        _access_deleted,
        sender=access_model,
        weak=False,
        dispatch_uid="work_hub.affiliation_access.post_delete",
    )
    pre_save.connect(
        _capture_user_before_save,
        sender=user_model,
        weak=False,
        dispatch_uid="work_hub.user.pre_save",
    )
    post_save.connect(
        _user_saved,
        sender=user_model,
        weak=False,
        dispatch_uid="work_hub.user.post_save",
    )
    pre_delete.connect(
        _capture_user_before_delete,
        sender=user_model,
        weak=False,
        dispatch_uid="work_hub.user.pre_delete",
    )
    post_delete.connect(
        _user_deleted,
        sender=user_model,
        weak=False,
        dispatch_uid="work_hub.user.post_delete",
    )
    post_save.connect(
        _affiliation_saved,
        sender=affiliation_model,
        weak=False,
        dispatch_uid="work_hub.affiliation.post_save",
    )
    pre_save.connect(
        _capture_user_access_before_change,
        sender=user_access_model,
        weak=False,
        dispatch_uid="work_hub.user_access.pre_save",
    )
    pre_delete.connect(
        _capture_user_access_before_change,
        sender=user_access_model,
        weak=False,
        dispatch_uid="work_hub.user_access.pre_delete",
    )
    post_save.connect(
        _user_access_changed,
        sender=user_access_model,
        weak=False,
        dispatch_uid="work_hub.user_access.post_save",
    )
    post_delete.connect(
        _user_access_changed,
        sender=user_access_model,
        weak=False,
        dispatch_uid="work_hub.user_access.post_delete",
    )
    pre_save.connect(
        _capture_scope_affiliation_grant_before_change,
        sender=scope_affiliation_grant_model,
        weak=False,
        dispatch_uid="work_hub.scope_affiliation_grant.pre_save",
    )
    pre_delete.connect(
        _capture_scope_affiliation_grant_before_change,
        sender=scope_affiliation_grant_model,
        weak=False,
        dispatch_uid="work_hub.scope_affiliation_grant.pre_delete",
    )
    post_save.connect(
        _scope_affiliation_grant_changed,
        sender=scope_affiliation_grant_model,
        weak=False,
        dispatch_uid="work_hub.scope_affiliation_grant.post_save",
    )
    post_delete.connect(
        _scope_affiliation_grant_changed,
        sender=scope_affiliation_grant_model,
        weak=False,
        dispatch_uid="work_hub.scope_affiliation_grant.post_delete",
    )
    pre_save.connect(
        _capture_policy_before_change,
        sender=access_policy_model,
        weak=False,
        dispatch_uid="work_hub.access_policy.pre_save",
    )
    pre_delete.connect(
        _capture_policy_before_change,
        sender=access_policy_model,
        weak=False,
        dispatch_uid="work_hub.access_policy.pre_delete",
    )
    post_save.connect(
        _access_policy_changed,
        sender=access_policy_model,
        weak=False,
        dispatch_uid="work_hub.access_policy.post_save",
    )
    post_delete.connect(
        _access_policy_changed,
        sender=access_policy_model,
        weak=False,
        dispatch_uid="work_hub.access_policy.post_delete",
    )
    pre_save.connect(
        _capture_scope_before_change,
        sender=access_scope_model,
        weak=False,
        dispatch_uid="work_hub.access_scope.pre_save",
    )
    pre_delete.connect(
        _capture_scope_before_change,
        sender=access_scope_model,
        weak=False,
        dispatch_uid="work_hub.access_scope.pre_delete",
    )
    post_save.connect(
        _access_scope_changed,
        sender=access_scope_model,
        weak=False,
        dispatch_uid="work_hub.access_scope.post_save",
    )
    post_delete.connect(
        _access_scope_changed,
        sender=access_scope_model,
        weak=False,
        dispatch_uid="work_hub.access_scope.post_delete",
    )
