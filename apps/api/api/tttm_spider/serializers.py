# =============================================================================
# 모듈: TTTM Spider 요청 직렬화
# 주요 클래스: DashboardQuerySerializer, ComboOptionsQuerySerializer
# 주요 가정: 외부 API 계약은 camelCase(dataType 등) + comp/ref 중첩 선택을 쓴다.
# =============================================================================
from __future__ import annotations

from rest_framework import serializers


class _CompSelectionSerializer(serializers.Serializer):
    line = serializers.CharField()
    eqp = serializers.CharField()
    chamber = serializers.CharField()
    date = serializers.CharField()
    type = serializers.CharField()


class _RefSelectionSerializer(serializers.Serializer):
    line = serializers.CharField()
    eqp = serializers.CharField()
    chamber = serializers.CharField()
    date = serializers.CharField()


class DashboardQuerySerializer(serializers.Serializer):
    """대시보드 번들 조회 요청."""

    comp = _CompSelectionSerializer()
    ref = _RefSelectionSerializer()
    dataType = serializers.CharField()
    stage = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    oesMethod = serializers.CharField(required=False, default="oob")
    traceRecipeId = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class SensorTraceRequestSerializer(serializers.Serializer):
    """센서(또는 OES step) 드릴다운 원파형/decomp 조회."""

    comp = _CompSelectionSerializer()
    ref = _RefSelectionSerializer()
    dataType = serializers.CharField()
    sensorKey = serializers.CharField()
    wlCenter = serializers.FloatField(required=False, default=387.0)
    wlHalfWidth = serializers.FloatField(required=False, default=1.0)


class ComboOptionsQuerySerializer(serializers.Serializer):
    """선택 캐스케이드 옵션 조회."""

    source = serializers.ChoiceField(choices=["comp", "ref"], default="comp")
    level = serializers.ChoiceField(choices=["line", "eqp", "chamber", "date"])
    line = serializers.CharField(required=False, allow_blank=True, default=None)
    eqp = serializers.CharField(required=False, allow_blank=True, default=None)
    chamber = serializers.CharField(required=False, allow_blank=True, default=None)
