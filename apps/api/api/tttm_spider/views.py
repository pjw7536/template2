# =============================================================================
# 모듈: TTTM Spider API 뷰
# 주요 엔드포인트: combo/options, combo/types, combo/data-types, dashboard/data
# 주요 가정: 로그인 사용자만 조회할 수 있다. 파이프라인은 돌리지 않고 결과 parquet만 읽는다.
# =============================================================================
from __future__ import annotations

try:
    import orjson

    def _fast_response(data, status: int = 200):
        from django.http import HttpResponse
        return HttpResponse(
            orjson.dumps(data),
            content_type="application/json; charset=utf-8",
            status=status,
        )
except ImportError:
    from rest_framework.response import Response as _DRFResponse

    def _fast_response(data, status: int = 200):
        return _DRFResponse(data, status=status)

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import (
    ComboOptionsQuerySerializer,
    DashboardQuerySerializer,
    SensorTraceRequestSerializer,
)


def _error_response(error: Exception) -> Response:
    status_code = getattr(error, "status_code", 400)
    return Response({"error": str(error)}, status=status_code)


class TttmSpiderComboOptionsView(APIView):
    """line/eqp/chamber/date 선택 캐스케이드 옵션."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        serializer = ComboOptionsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            return _fast_response(services.get_combo_options(v["level"], v["line"], v["eqp"], v["chamber"]))
        except services.TttmSpiderServiceError as error:
            return _error_response(error)


class TttmSpiderLotwfView(APIView):
    """(eqp, chamber)에서 진행된 lotwf 목록."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        eqp = request.query_params.get("eqp", "")
        chamber = request.query_params.get("chamber", "")
        if not eqp or not chamber:
            return Response({"error": "eqp, chamber가 필요합니다."}, status=400)
        try:
            return _fast_response(services.get_target_lotwf(eqp, chamber))
        except services.TttmSpiderServiceError as error:
            return _error_response(error)


class TttmSpiderResultStatusView(APIView):
    """조합별 계산 결과 존재 여부(재계산 활성화 판단용)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        items = request.data.get("items", []) if isinstance(request.data, dict) else []
        return _fast_response(services.get_result_status(items))


class TttmSpiderEqpsView(APIView):
    """전체 eqp 목록(자동완성용)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        return _fast_response(services.get_eqps())


class TttmSpiderChambersView(APIView):
    """eqp 에 존재하는 chamber 목록(eqp만 입력하고 추가 시 전체 챔버)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        eqp = request.query_params.get("eqp", "")
        if not eqp:
            return Response({"error": "eqp가 필요합니다."}, status=400)
        try:
            return _fast_response(services.get_chambers_for_eqp(eqp))
        except services.TttmSpiderServiceError as error:
            return _error_response(error)


class TttmSpiderGoldenLotwfView(APIView):
    """타설비검증 REF 후보(골든 챔버 lotwf)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        recipe = request.query_params.get("recipe", "") or None
        try:
            return _fast_response(services.get_golden_lotwf(recipe))
        except services.TttmSpiderServiceError as error:
            return _error_response(error)


class TttmSpiderComboTypesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        return _fast_response(services.get_type_options())


class TttmSpiderComboDataTypesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        return _fast_response(services.get_data_type_options())


class TttmSpiderDashboardDataView(APIView):
    """scores.parquet 을 읽어 대시보드 번들(JSON)로."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = DashboardQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            bundle = services.build_dashboard_bundle(
                ref=dict(v["ref"]),
                comp=dict(v["comp"]),
                data_type=v["dataType"],
                stage=v.get("stage"),
                oes_method=v.get("oesMethod", "oob"),
                trace_recipe_id=v.get("traceRecipeId"),
            )
            return _fast_response({
                "bundle": bundle,
                "name": f"{v['comp']['eqp']}-{v['comp']['chamber']}",
            })
        except services.TttmSpiderServiceError as error:
            return _error_response(error)


class TttmSpiderSensorTraceView(APIView):
    """센서(또는 OES step) 드릴다운 원파형/decomp."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = SensorTraceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            return _fast_response(services.build_sensor_trace_response(
                ref=dict(v["ref"]), comp=dict(v["comp"]),
                data_type=v["dataType"], sensor_key=v["sensorKey"],
            ))
        except services.TttmSpiderServiceError as error:
            return _error_response(error)
