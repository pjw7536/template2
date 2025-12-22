from __future__ import annotations

from django.urls import path

from .views import (
    AccountAffiliationApprovalView,
    AccountAffiliationView,
    AccountAffiliationJiraKeyView,
    AccountAffiliationRequestListView,
    AccountAffiliationReconfirmView,
    AccountExternalAffiliationSyncView,
    AccountGrantListView,
    AccountGrantView,
    AccountOverviewView,
    LineSdwtOptionsView,
)

urlpatterns = [
    path("overview", AccountOverviewView.as_view(), name="account-overview"),
    path("affiliation", AccountAffiliationView.as_view(), name="account-affiliation"),
    path(
        "affiliation/approve",
        AccountAffiliationApprovalView.as_view(),
        name="account-affiliation-approve",
    ),
    path(
        "affiliation/requests",
        AccountAffiliationRequestListView.as_view(),
        name="account-affiliation-requests",
    ),
    path(
        "affiliation/reconfirm",
        AccountAffiliationReconfirmView.as_view(),
        name="account-affiliation-reconfirm",
    ),
    path(
        "affiliation/jira-key",
        AccountAffiliationJiraKeyView.as_view(),
        name="account-affiliation-jira-key",
    ),
    path(
        "external-affiliations/sync",
        AccountExternalAffiliationSyncView.as_view(),
        name="account-external-affiliation-sync",
    ),
    path("access/grants", AccountGrantView.as_view(), name="account-access-grant"),
    path("access/manageable", AccountGrantListView.as_view(), name="account-access-manageable"),
    path("line-sdwt-options", LineSdwtOptionsView.as_view(), name="account-line-sdwt-options"),
]
