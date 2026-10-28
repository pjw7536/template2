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
        (root / 'docs').mkdir()
        (root / 'docs/inventory.md').write_text(inventory)
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
