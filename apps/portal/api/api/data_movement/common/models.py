"""data movement 앱들이 공유하는 Django model field입니다."""

from __future__ import annotations

from django.db import models


class UnboundedNumericField(models.Field):
    """precision과 scale 제한이 없는 PostgreSQL numeric 컬럼을 표현합니다."""

    description = "PostgreSQL unbounded numeric"

    def db_type(self, connection) -> str:
        """PostgreSQL의 제약 없는 numeric DB type을 반환합니다."""

        return "numeric"
