from __future__ import annotations

from rest_framework import serializers


class HardSpecQuerySerializer(serializers.Serializer):
    """Hard Limit 추천 조회 조건을 검증합니다."""

    lineId = serializers.CharField(required=True, allow_blank=False)
    stepSeq = serializers.CharField(required=True, allow_blank=False)
    recipeId = serializers.CharField(required=True, allow_blank=False)
    fdcModel = serializers.CharField(required=True, allow_blank=False)


class HardSpecMetaQuerySerializer(serializers.Serializer):
    """Hard Limit 선택 옵션 조회 조건을 검증합니다."""

    lineId = serializers.CharField(required=False, allow_blank=True)
    stepSeq = serializers.CharField(required=False, allow_blank=True)
    recipeId = serializers.CharField(required=False, allow_blank=True)
