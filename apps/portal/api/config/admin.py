from __future__ import annotations

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class SuperuserAdminSite(AdminSite):
    site_header = "Etch AX Portal Administration"
    site_title = "Etch AX Portal"
    index_title = "Admin"

    def has_permission(self, request) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_active and user.is_superuser)


class SuperuserAdminConfig(AdminConfig):
    default_site = "config.admin.SuperuserAdminSite"

