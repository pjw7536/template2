from __future__ import annotations

from django.urls import path

from .views import (
    AccountAffiliationApprovalView,
    AccountAffiliationView,
    AccountGrantListView,
    AccountGrantView,
    LineSdwtOptionsView,
)

urlpatterns = [
    path("affiliation", AccountAffiliationView.as_view(), name="account-affiliation"),
    path(
        "affiliation/approve",
        AccountAffiliationApprovalView.as_view(),
        name="account-affiliation-approve",
    ),
    path("access/grants", AccountGrantView.as_view(), name="account-access-grant"),
    path("access/manageable", AccountGrantListView.as_view(), name="account-access-manageable"),
    path("line-sdwt-options", LineSdwtOptionsView.as_view(), name="account-line-sdwt-options"),
]

