"""문서 검사에서 누락됐던 URL 문법과 모듈 간 오탐을 검증합니다."""

import tempfile
import unittest
from pathlib import Path

from apps.tooling.agent import check_docs_routes as audit


class DocsRoutesTests(unittest.TestCase):
    def test_multiline_single_quotes_and_converters_are_read(self):
        source = '''
urlpatterns = [
    path('items', ItemView.as_view()),
    path(
        "items/<int:item_id>/",
        DetailView.as_view(),
    ),
    path("", RootView.as_view()),
]
example = path("unused-example", ExampleView.as_view())
'''
        self.assertEqual(audit.read_routes(source), {"items", "items/<item_id>"})

    def make_root(self, directory, source, inventory):
        root = Path(directory)
        path = root / 'apps/portal/api/api/example/urls.py'
        path.parent.mkdir(parents=True)
        path.write_text(source)
        (root / 'docs/reference').mkdir(parents=True)
        (root / 'docs/reference/02-inventory.md').write_text(inventory)
        return root

    def test_matching_module_row_accepts_optional_trailing_slashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = [path("items/", View)]',
                '| Example | `/api/v1/example/` | `apps/portal/api/api/example/urls.py` | `items` |')
            self.assertFalse(audit.check_inventory(root))

    def test_text_elsewhere_cannot_hide_a_missing_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = [path("items", View)]',
                '| Example | `/api/v1/example/` | `apps/portal/api/api/example/urls.py` | `items-old` |\n'
                '| Other | `/api/v1/other/` | `other.py` | `items` |\nitems')
            findings = audit.check_inventory(root)
            self.assertEqual(len(findings), 2)
            self.assertTrue(any('색인 누락: items' in value for value in findings))
            self.assertTrue(any('잘못된 endpoint 색인: items-old' in value for value in findings))

    def test_missing_module_row_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = [path("items", View)]', '')
            self.assertEqual(len(audit.check_inventory(root)), 1)


    def test_callback_route_is_checked_alongside_business_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = []',
                '| Example | `/api/v1/example/` | `apps/portal/api/api/example/urls.py` | |')
            callback = root / 'apps/portal/api/api/example/callback_urls.py'
            callback.write_text('urlpatterns = [path("keycloak/callback/", View)]')
            self.assertEqual(len(audit.check_inventory(root)), 1)
            inventory = root / 'docs/reference/02-inventory.md'
            inventory.write_text(inventory.read_text() + '\n'
                '| Callback | `/auth/` | `apps/portal/api/api/example/callback_urls.py` | `keycloak/callback/` |')
            self.assertFalse(audit.check_inventory(root))

    def test_model_parser_excludes_choices_and_ordinary_classes(self):
        source = 'class Item(models.Model): pass\nclass User(AbstractBaseUser): pass\n'
        source += 'class Kind(models.TextChoices): pass\nclass Helper: pass\n'
        self.assertEqual(audit.read_model_names(source), {'Item', 'User'})

    def test_nested_model_index_reports_missing_stale_and_duplicate_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = []',
                '| `api.data_movement.items` | `Item`, `Item`, `Removed` |')
            model = root / 'apps/portal/api/api/data_movement/items/models.py'
            model.parent.mkdir(parents=True)
            model.write_text('class Item(models.Model): pass\nclass LoadJob(models.Model): pass\n')
            findings = audit.check_models(root)
            self.assertEqual(len(findings), 3)
            self.assertTrue(any('누락: LoadJob' in item for item in findings))
            self.assertTrue(any('잘못된 모델 색인: Removed' in item for item in findings))
            self.assertTrue(any('모델 중복: Item' in item for item in findings))
            (root / 'docs/reference/02-inventory.md').write_text(
                '| `api.data_movement.items` | `Item`, `LoadJob` |')
            self.assertFalse(audit.check_models(root))

    def test_command_name_in_prose_cannot_replace_an_exact_index_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = []', 'load_items')
            command = root / 'apps/portal/api/api/example/management/commands/load_items.py'
            command.parent.mkdir(parents=True)
            command.write_text('')
            self.assertEqual(len(audit.check_commands(root)), 1)
            row = '| `load_items` | `apps/portal/api/api/example/management/commands/load_items.py` | test |'
            inventory = root / 'docs/reference/02-inventory.md'
            inventory.write_text(row)
            self.assertFalse(audit.check_commands(root))
            inventory.write_text(row + '\n' + row)
            self.assertEqual(len(audit.check_commands(root)), 1)

    def test_deleted_command_cannot_remain_in_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = []',
                '| `removed` | `apps/portal/api/api/example/management/commands/removed.py` | test |')
            self.assertEqual(len(audit.check_commands(root)), 1)

    def test_feature_must_have_a_single_row_in_both_guides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_root(directory, 'urlpatterns = []', '')
            feature = root / 'apps/portal/web/src/features/example/routes.jsx'
            feature.parent.mkdir(parents=True)
            feature.write_text('export const routes = []')
            modules = root / 'docs/modules/README.md'
            modules.parent.mkdir(parents=True)
            modules.write_text('example')
            self.assertEqual(len(audit.check_frontend_features(root)), 2)
            row = '| `apps/portal/web/src/features/example/routes.jsx` |'
            inventory = root / 'docs/reference/02-inventory.md'
            inventory.write_text(row)
            modules.write_text('| 기능 | `example` |')
            self.assertFalse(audit.check_frontend_features(root))
            inventory.write_text(row + '\n' + row)
            self.assertEqual(len(audit.check_frontend_features(root)), 1)
