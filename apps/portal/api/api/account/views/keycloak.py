"""Keycloak 관리 계정의 조회와 종료된 권한 변경 API를 제공합니다."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view

from api.common.services import api_error_response
from .. import services


@csrf_exempt
def managed_by_keycloak(request, **kwargs):
    """POST /api/v1/account/access/request 등 종료 API는 입력과 무관하게 410입니다."""
    return api_error_response(code="managed_by_keycloak",
        message="소속과 권한은 Keycloak에서 관리합니다. 관리자에게 별도로 요청하세요.", status=410)


@api_view(["GET"])
def keycloak_account_overview(request):
    """GET /api/v1/account/overview는 현재 세션의 소속·권한을 반환합니다."""
    context = services.get_authorization_context(user=request.user)
    return JsonResponse({
        "authorizationSource": "keycloak", "hasAllAppsAccess": context.all_apps,
        "isPortalAdmin": context.portal_admin, "department": context.department,
        "userSdwtProd": context.user_sdwt_prod, "line": context.line,
        "sdwtAccess": dict(context.sdwt_roles),
        "scopeAccess": services.get_scope_access_payloads(user=request.user, context=context),
    })


@api_view(["GET"])
def keycloak_line_sdwt_options(request):
    """GET /api/v1/account/line-sdwt-options는 본인 line과 접근 가능한 SDWT만 제공합니다."""
    context = services.get_authorization_context(user=request.user)
    values = sorted(dict(context.sdwt_roles))
    lines = [{"lineId": context.line, "userSdwtProds": [context.user_sdwt_prod]}] if context.line and context.user_sdwt_prod in values else []
    return JsonResponse({"lines": lines, "userSdwtProds": values})
