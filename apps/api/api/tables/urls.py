from __future__ import annotations

from django.urls import path

from .views import TableUpdateView, TablesView

urlpatterns = [
    path("", TablesView.as_view(), name="tables"),
    path("update", TableUpdateView.as_view(), name="tables-update"),
]

