from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agent import check_backend_boundaries as backend_audit
from scripts.agent import check_frontend_boundaries as frontend_audit


class BackendBoundaryAuditTests(unittest.TestCase):
    """Backend 경계 감사에서 과거 우회 형태를 회귀 검증합니다."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.api_root = Path(self.temp_dir.name) / "api"
        self.api_root.mkdir()
        self.api_root_patch = mock.patch.object(backend_audit, "API_ROOT", self.api_root)
        self.api_root_patch.start()

    def tearDown(self):
        self.api_root_patch.stop()
        self.temp_dir.cleanup()

    def write_source(self, relative_path: str, source: str) -> Path:
        """임시 backend source를 생성합니다."""

        path = self.api_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def test_relative_cross_domain_internal_import_is_rejected(self):
        self.write_source("auth/worker.py", "from ..account.models import User\n")

        findings = backend_audit.check_import_boundaries()

        self.assertEqual(len(findings), 1)
        self.assertIn("api.account.models", findings[0].message)

    def test_relative_cross_domain_facade_import_is_allowed(self):
        self.write_source("auth/worker.py", "from ..account.services import ensure_access_scope\n")

        self.assertEqual(backend_audit.check_import_boundaries(), [])

    def test_view_package_member_with_direct_orm_is_rejected(self):
        self.write_source("account/views/detail.py", "rows = User.objects.all()\n")

        findings = backend_audit.check_view_orm_usage()

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path.name, "detail.py")

    def test_selector_package_member_with_write_is_rejected(self):
        self.write_source("account/selectors/update.py", "User.objects.create(username='tester')\n")

        findings = backend_audit.check_selector_writes()

        self.assertEqual(len(findings), 1)
        self.assertIn("create()", findings[0].message)

    def test_unrelated_nested_views_name_is_not_treated_as_view_layer(self):
        self.write_source("account/services/views/helper.py", "rows = User.objects.all()\n")

        self.assertEqual(backend_audit.check_view_orm_usage(), [])


class FrontendBoundaryAuditTests(unittest.TestCase):
    """Frontend import 형태별 facade와 의존 방향 검사를 회귀 검증합니다."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.web_src = self.root_dir / "apps" / "web" / "src"
        self.features_dir = self.web_src / "features"
        self.features_dir.mkdir(parents=True)
        self.patches = [
            mock.patch.object(frontend_audit, "ROOT_DIR", self.root_dir),
            mock.patch.object(frontend_audit, "WEB_SRC", self.web_src),
            mock.patch.object(frontend_audit, "FEATURES_DIR", self.features_dir),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()

    def write_source(self, relative_path: str, source: str) -> Path:
        """임시 frontend source를 생성합니다."""

        path = self.web_src / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def test_import_specifier_collection_covers_supported_forms(self):
        source = """
import { accountApi } from "@/features/account"
import "@/features/account/api/accountApi"
const module = import("@/features/emails")
export { routes } from "@/features/auth"
"""

        specifiers = [specifier for specifier, _position in frontend_audit.iter_import_specifiers(source)]

        self.assertEqual(
            specifiers,
            [
                "@/features/account",
                "@/features/account/api/accountApi",
                "@/features/emails",
                "@/features/auth",
            ],
        )

    def test_relative_cross_feature_internal_import_is_rejected(self):
        self.write_source(
            "features/auth/components/Gate.jsx",
            'import { accountApi } from "../../account/api/accountApi"\n',
        )

        internal, dependencies, _graph = frontend_audit.check_feature_imports()

        self.assertEqual(len(internal), 1)
        self.assertIn("../../account/api/accountApi", internal[0])
        self.assertEqual(dependencies, [])

    def test_relative_cross_feature_facade_path_is_rejected(self):
        self.write_source(
            "features/auth/components/Gate.jsx",
            'import { accountApi } from "../../account"\n',
        )

        internal, dependencies, _graph = frontend_audit.check_feature_imports()

        self.assertEqual(len(internal), 1)
        self.assertEqual(dependencies, [])

    def test_side_effect_internal_import_is_rejected(self):
        self.write_source(
            "features/auth/components/Gate.jsx",
            'import "@/features/account/api/accountApi"\n',
        )

        internal, _dependencies, _graph = frontend_audit.check_feature_imports()

        self.assertEqual(len(internal), 1)

    def test_declared_alias_facade_dependency_is_allowed(self):
        self.write_source(
            "features/line-dashboard/components/Shell.jsx",
            'import { accountApi } from "@/features/account"\n',
        )

        internal, dependencies, graph = frontend_audit.check_feature_imports()

        self.assertEqual(internal, [])
        self.assertEqual(dependencies, [])
        self.assertEqual(graph["line-dashboard"], {"account"})

    def test_undeclared_alias_facade_dependency_is_rejected(self):
        self.write_source(
            "features/account/components/Panel.jsx",
            'import { authRoutes } from "@/features/auth"\n',
        )

        internal, dependencies, graph = frontend_audit.check_feature_imports()

        self.assertEqual(internal, [])
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(graph["account"], {"auth"})

    def test_dependency_cycle_is_reported(self):
        graph = {"account": {"auth"}, "auth": {"account"}}

        self.assertEqual(frontend_audit.find_cycle(graph), ["account", "auth", "account"])


if __name__ == "__main__":
    unittest.main()
