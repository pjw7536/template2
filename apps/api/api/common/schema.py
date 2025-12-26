"""OpenAPI schema helpers."""
from __future__ import annotations

from typing import Optional

from drf_spectacular.openapi import AutoSchema


class FeatureAutoSchema(AutoSchema):
    """Group OpenAPI operations by Django app (api.<feature>)."""

    def get_tags(self) -> list[str]:
        feature_tag = self._get_feature_tag()
        if feature_tag:
            return [feature_tag]
        return super().get_tags()

    def _get_feature_tag(self) -> Optional[str]:
        module = getattr(self.view, "__module__", "") or getattr(
            getattr(self.view, "__class__", None), "__module__", ""
        )
        if not module:
            return None
        parts = module.split(".")
        if len(parts) >= 2 and parts[0] == "api":
            return parts[1]
        return None
