from __future__ import annotations

from typing import Any, Iterable


def serialize_user(user: Any) -> dict[str, Any] | None:
    """작성자 정보를 API 응답 형태로 직렬화합니다."""

    if not user:
        return None
    name = (user.get_full_name() or "").strip() or user.get_username() or user.email
    payload: dict[str, Any] = {"id": user.pk, "name": name or "사용자"}
    if user.email:
        payload["email"] = user.email
    return payload


def serialize_reply(reply: Any) -> dict[str, Any]:
    """답변(VocReply)을 API 응답 형태로 직렬화합니다."""

    return {
        "id": reply.pk,
        "postId": reply.post_id,
        "content": reply.content,
        "createdAt": reply.created_at.isoformat(),
        "author": serialize_user(getattr(reply, "author", None)),
    }


def _prefetched_replies(post: Any) -> Iterable[dict[str, Any]]:
    """prefetch_related 결과를 활용해 답변을 직렬화합니다."""

    related = getattr(post, "replies", None)
    if related is None:
        return []
    return [serialize_reply(reply) for reply in related.all()]


def serialize_post(post: Any) -> dict[str, Any]:
    """게시글(VocPost)을 API 응답 형태로 직렬화합니다."""

    return {
        "id": post.pk,
        "title": post.title,
        "content": post.content,
        "status": post.status,
        "createdAt": post.created_at.isoformat(),
        "updatedAt": post.updated_at.isoformat(),
        "author": serialize_user(getattr(post, "author", None)),
        "replies": list(_prefetched_replies(post)),
    }


__all__ = ["serialize_post", "serialize_reply", "serialize_user"]
