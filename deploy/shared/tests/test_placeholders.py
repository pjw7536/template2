"""Python·bash 검사가 같은 자리표시자 규칙을 사용하는지 확인합니다."""

import importlib.util
from pathlib import Path
import re
import subprocess
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('shared_runtime', SCRIPTS / 'runtime.py')
RUNTIME = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUNTIME)

CASES = {
    'replace-me': True,
    'replace-here-before-deploy': True,
    'change-me-later': True,
    'https://sso.example.invalid/realms/etch': True,
    '<token>': True,
    'Bearer <token>': True,
    'https://<host>/realms/etch': True,
    '<namespace>/<secret>': True,
    '<입력 필요>': True,
    'Str0ng!pass<word': False,
    'a>b<c': False,
    'https://sso.etch.samsungds.net/realms/etch': False,
}


def bash_is_placeholder(value):
    """env-lib.sh의 판정을 그대로 실행한다."""
    script = f'source "{SCRIPTS / "env-lib.sh"}"; is_placeholder "$1"'
    return subprocess.run(['bash', '-c', script, 'test', value]).returncode == 0


class PlaceholderTests(unittest.TestCase):
    def test_marker_lists_match(self):
        text = (SCRIPTS / 'env-lib.sh').read_text()
        markers = re.search(r'^PLACEHOLDER_MARKERS=\(([^)]*)\)', text, re.M).group(1).split()
        self.assertEqual(tuple(markers), RUNTIME.PLACEHOLDER_MARKERS)

    def test_python_and_bash_agree(self):
        for value, expected in CASES.items():
            with self.subTest(value=value):
                self.assertEqual(RUNTIME.is_placeholder(value), expected)
                self.assertEqual(bash_is_placeholder(value), expected)


if __name__ == '__main__':
    unittest.main()
