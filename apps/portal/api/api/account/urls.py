"""Account의 조회와 종료된 Keycloak 관리 경로를 명시적으로 등록합니다."""
from django.urls import path
from .views.user_pool import AccountUserPoolView
from .views.keycloak import managed_by_keycloak, keycloak_account_overview, keycloak_line_sdwt_options

urlpatterns = [
    path('overview', keycloak_account_overview, name='account-overview'),
    path('affiliation', managed_by_keycloak, name='account-affiliation'),
    path('affiliation/approve', managed_by_keycloak, name='account-affiliation-approve'),
    path('affiliation/requests', managed_by_keycloak, name='account-affiliation-requests'),
    path('affiliation/members', managed_by_keycloak, name='account-affiliation-members'),
    path('affiliation/access', managed_by_keycloak, name='account-affiliation-access'),
    path('affiliation/reconfirm', managed_by_keycloak, name='account-affiliation-reconfirm'),
    path('access/request', managed_by_keycloak, name='account-access-request'),
    path('access/users', keycloak_account_overview, name='account-access-users'),
    path('access/matrix', keycloak_account_overview, name='account-access-matrix'),
    path('access/pending-requests', managed_by_keycloak, name='account-pending-access-requests'),
    path('access/pending-requests/bulk-approve', managed_by_keycloak, name='account-pending-access-requests-bulk-approve'),
    path('access/users/<int:user_id>/decision', managed_by_keycloak, name='account-access-user-decision'),
    path('access/users/<int:user_id>/data-scope', managed_by_keycloak, name='account-access-user-data-scope'),
    path('access/users/<int:user_id>/apply-all', managed_by_keycloak, name='account-access-user-apply-all'),
    path('access/policy-rules', managed_by_keycloak, name='account-access-policy-rules'),
    path('access/policy-rules/bulk-apply', managed_by_keycloak, name='account-access-policy-rules-bulk-apply'),
    path('access/policy-rules/<int:rule_id>', managed_by_keycloak, name='account-access-policy-rule-detail'),
    path('access/audit-logs', managed_by_keycloak, name='account-access-audit-logs'),
    path('external-affiliations/sync', managed_by_keycloak, name='account-external-affiliation-sync'),
    path('users', AccountUserPoolView.as_view(), name='account-users'),
    path('line-sdwt-options', keycloak_line_sdwt_options, name='account-line-sdwt-options'),
]
