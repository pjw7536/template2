"""공용 인증 입력의 덮어쓰기 범위, 권한, 실패 시 보존을 검증합니다."""

from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'scripts'))
from prepare_identity_env import ROOT, prepare, read_env  # noqa: E402


class IdentityEnvTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.identity = root / 'identity.env'
        self.keycloak = root / 'keycloak.env'
        self.iam = root / 'iam.env'
        self.identity.write_text('CORP_OIDC_CLIENT_ID=new-id\nCORP_OIDC_CLIENT_SECRET=opaque=a#b\n'
                                 'IAM_PLATFORM_ADMIN_USERNAMES=101,102\n')
        self.identity.chmod(0o600)
        self.keycloak.write_text('postgres-password=db-fixture\nbootstrap-admin-password=admin-fixture\n'
                                 'CORP_OIDC_CLIENT_ID=old-id\nCORP_OIDC_DISCOVERY_URL=https://sso.example.test\n')
        self.iam.write_text('IAM_STORAGE_NODE=worker-a\nIAM_PLATFORM_ADMIN_USERNAMES=99\n')

    def test_make_outputs_paths_and_keeps_existing_app_values(self):
        command = ['make', '-s', 'identity-env-prepare', f'IDENTITY_ENV={self.identity}',
                   f'KEYCLOAK_ENV={self.keycloak}', f'IAM_ENV={self.iam}']
        inputs = [path.read_bytes() for path in (self.identity, self.keycloak, self.iam)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        paths = dict(line.split('=', 1) for line in result.stdout.splitlines())
        self.assertEqual(paths.keys(), {'KEYCLOAK_ENV', 'IAM_ENV'})
        keycloak, iam = (Path(paths[key]) for key in ('KEYCLOAK_ENV', 'IAM_ENV'))
        self.assertEqual(stat.S_IMODE(keycloak.parent.stat().st_mode), 0o700)
        for file in (keycloak, iam):
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        self.assertEqual(read_env(keycloak), {**read_env(self.keycloak), 'CORP_OIDC_CLIENT_ID': 'new-id',
                                            'CORP_OIDC_CLIENT_SECRET': 'opaque=a#b'})
        self.assertEqual(read_env(iam), {**read_env(self.iam), 'IAM_PLATFORM_ADMIN_USERNAMES': '101,102'})
        self.assertEqual(inputs, [path.read_bytes() for path in (self.identity, self.keycloak, self.iam)])

    def test_optional_admin_override_and_invalid_input_keep_previous_files(self):
        required = 'CORP_OIDC_CLIENT_ID=another-id\nCORP_OIDC_CLIENT_SECRET=another-secret\n'
        self.identity.write_text(required)
        output = prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(read_env(output / 'iam.env')['IAM_PLATFORM_ADMIN_USERNAMES'], '99')
        self.identity.write_text(required + 'IAM_PLATFORM_ADMIN_USERNAMES=\n')
        self.assertEqual(prepare(self.identity, self.keycloak, self.iam), output)
        self.assertEqual(read_env(output / 'iam.env')['IAM_PLATFORM_ADMIN_USERNAMES'], '')
        previous = [(output / name).read_bytes() for name in ('keycloak.env', 'iam.env')]
        self.identity.write_text(required + 'bootstrap-admin-password=unexpected\n')
        with self.assertRaisesRegex(ValueError, '키만 사용할'):
            prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(previous, [(output / name).read_bytes() for name in ('keycloak.env', 'iam.env')])

    def test_public_input_and_generated_base_are_rejected(self):
        output = prepare(self.identity, self.keycloak, self.iam)
        with self.assertRaisesRegex(ValueError, '생성본은 원본으로'):
            prepare(self.identity, output / 'keycloak.env', self.iam)
        self.identity.chmod(0o644)
        with self.assertRaisesRegex(ValueError, '0600'):
            prepare(self.identity, self.keycloak, self.iam)
