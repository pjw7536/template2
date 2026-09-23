"""일반 env와 비밀값 파일 병합의 Python·Bash 계약을 검증한다."""

from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MERGE = runpy.run_path(str(ROOT / 'deploy/shared/scripts/env_secrets.py'))['merge_secrets']


class EnvSecretsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'input.env'
        self.path.write_text('PASSWORD=\nHOST=server.test\n')
        self.secret = self.path.with_suffix('.secrets.env')

    def shell(self):
        return subprocess.run(
            ['bash', '-c', 'set -eu; source "$1"; load_env "$2"; printf "%s" "${ENV_VALUES[PASSWORD]}"',
             'bash', str(ROOT / 'deploy/shared/scripts/env-lib.sh'), str(self.path)],
            capture_output=True, text=True)

    def test_merges_without_executing_and_preserves_general_values(self):
        marker = Path(self.directory.name) / 'must-not-exist'
        value = f'$(touch {marker})'
        self.secret.write_text(f'PASSWORD={value}\n')
        self.assertEqual(MERGE(self.path, {'PASSWORD': '', 'HOST': 'server.test'}),
                         {'PASSWORD': value, 'HOST': 'server.test'})
        result = self.shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, value)
        self.assertFalse(marker.exists())

    def test_rejects_unknown_duplicate_and_malformed_keys(self):
        for content in ['TYPO=value\n', 'PASSWORD=a\nPASSWORD=b\n', '=invalid\n', 'PASSWORD\n']:
            with self.subTest(content=content):
                self.secret.write_text(content)
                with self.assertRaises(ValueError):
                    MERGE(self.path, {'PASSWORD': '', 'HOST': 'server.test'})
                self.assertNotEqual(self.shell().returncode, 0)

    def test_missing_secrets_preserves_blank_for_required_validation(self):
        self.assertEqual(MERGE(self.path, {'PASSWORD': ''}), {'PASSWORD': ''})
        self.assertEqual(self.shell().stdout, '')

    def test_examples_do_not_load_adjacent_secrets(self):
        self.secret.write_text('PASSWORD=private-fixture\n')
        self.path = self.path.with_suffix('.env.example')
        self.path.write_text('PASSWORD=\nHOST=server.test\n')
        self.assertEqual(MERGE(self.path, {'PASSWORD': ''}), {'PASSWORD': ''})
        self.assertEqual(self.shell().stdout, '')


if __name__ == '__main__':
    unittest.main()
