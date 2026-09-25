"""단일 env를 실행 없이 읽고 중복·잘못된 입력을 거부하는 계약을 검증합니다."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class EnvLoadingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'input.env'

    def shell(self):
        return subprocess.run(
            ['bash', '-c', 'set -eu; source "$1"; load_env "$2"; printf "%s" "${ENV_VALUES[PASSWORD]}"',
             'bash', str(ROOT / 'deploy/shared/scripts/env-lib.sh'), str(self.path)],
            capture_output=True, text=True)

    def test_reads_literal_values_without_executing(self):
        marker = Path(self.directory.name) / 'must-not-exist'
        value = f'$(touch {marker})'
        self.path.write_text(f'PASSWORD={value}\nHOST=server.test\n')
        result = self.shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, value)
        self.assertFalse(marker.exists())

    def test_rejects_duplicate_and_malformed_keys(self):
        for content in ['PASSWORD=a\nPASSWORD=b\n', '=invalid\n', 'PASSWORD\n']:
            with self.subTest(content=content):
                self.path.write_text(content)
                self.assertNotEqual(self.shell().returncode, 0)

    def test_does_not_override_from_adjacent_file(self):
        self.path.write_text('PASSWORD=current-value\n')
        self.path.with_suffix('.secrets.env').write_text('PASSWORD=stale-value\n')
        result = self.shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'current-value')


if __name__ == '__main__':
    unittest.main()
