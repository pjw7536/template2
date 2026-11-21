"""공용 인증 입력의 덮어쓰기 범위, 권한, 실패 시 보존을 검증합니다."""

from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / 'scripts'))
from prepare_identity_env import APP_OVERRIDES, INPUT_KEYS, ROOT, inputs, prepare, read_catalog, read_env  # noqa: E402


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

    def test_make_uses_checkout_root_by_default(self):
        checkout = self.identity.parent
        for name in ('Makefile', 'deploy/iam/scripts/prepare_identity_env.py', 'deploy/shared/scripts/runtime.py',
                     'deploy/shared/scripts/image_registry.py', 'deploy/shared/scripts/catalog.py',
                     'deploy/shared/apps.json'):
            destination = checkout / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        command = ['make', '-s', 'identity-env-prepare', f'KEYCLOAK_ENV={self.keycloak}', f'IAM_ENV={self.iam}']
        self.identity.chmod(0o644)
        generated = checkout / 'identity.env.generated'
        result = subprocess.run(command, cwd=checkout, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0600', result.stderr)
        self.assertFalse(generated.exists())

        self.identity.chmod(0o600)
        result = subprocess.run(command, cwd=checkout, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), [f'KEYCLOAK_ENV={generated / "keycloak.env"}',
                                                     f'IAM_ENV={generated / "iam.env"}'])
        self.assertEqual(read_env(generated / 'keycloak.env')['CORP_OIDC_CLIENT_SECRET'], 'opaque=a#b')
        self.assertEqual(read_env(generated / 'iam.env')['IAM_PLATFORM_ADMIN_USERNAMES'], '101,102')

        self.identity.write_text('CORP_OIDC_CLIENT_ID=new-id\nCORP_OIDC_CLIENT_SECRET=\n')
        private_input = checkout / 'identity.env.local'
        private_input.write_text('CORP_OIDC_CLIENT_SECRET=legacy-secret\n')
        private_input.chmod(0o600)
        result = subprocess.run(command, cwd=checkout, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity.env의 CORP_OIDC_CLIENT_SECRET', result.stderr)
        self.assertEqual(read_env(generated / 'keycloak.env')['CORP_OIDC_CLIENT_SECRET'], 'opaque=a#b')

    def test_make_routes_linked_apps_and_ca_with_no_corp_oidc_override(self):
        parent = self.identity.parent
        headlamp, airflow, portal, ca = (parent / name for name in ('headlamp', 'airflow', 'portal', 'ca.pem'))
        headlamp.write_text('HEADLAMP_ADMINS=old-admin\nHEADLAMP_HOST=headlamp.example.test\n')
        airflow.write_text('AIRFLOW_OIDC_CLIENT_ID=existing-airflow\nPOSTGRES_PASSWORD=retained\n')
        portal.write_text('OIDC_CLIENT_ID=existing-portal\nDJANGO_DB_NAME=retained\n')
        ca.touch()
        self.identity.write_text('CORP_OIDC_CLIENT_ID=\nCORP_OIDC_CLIENT_SECRET=\nHEADLAMP_ADMINS=100,200\n'
                                 'AIRFLOW_OIDC_CLIENT_SECRET=new-airflow-secret\nPORTAL_OIDC_CLIENT_ID=portal-client\n'
                                 'PORTAL_OIDC_CLIENT_SECRET=new-portal-secret\nHEADLAMP_OIDC_CA_FILE=ca.pem\n')
        command = ['make', '-s', 'identity-env-prepare', f'IDENTITY_ENV={self.identity}',
                   f'KEYCLOAK_ENV={self.keycloak}', f'IAM_ENV={self.iam}', f'HEADLAMP_ENV={headlamp}',
                   f'AIRFLOW_ENV={airflow}', f'PROD_API_ENV_FILE={portal}']
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        paths = {key: Path(value) for key, value in (line.split('=', 1) for line in result.stdout.splitlines())}
        self.assertEqual(paths['HEADLAMP_OIDC_CA_FILE'], ca)
        self.assertEqual(read_env(paths['HEADLAMP_ENV']), {**read_env(headlamp), 'HEADLAMP_ADMINS': '100,200'})
        self.assertEqual(read_env(paths['AIRFLOW_ENV']),
                         {**read_env(airflow), 'AIRFLOW_OIDC_CLIENT_SECRET': 'new-airflow-secret'})
        self.assertEqual(read_env(paths['PROD_API_ENV_FILE']),
                         {**read_env(portal), 'OIDC_CLIENT_ID': 'portal-client', 'OIDC_CLIENT_SECRET': 'new-portal-secret'})
        self.assertEqual(read_env(paths['KEYCLOAK_ENV']), read_env(self.keycloak))
        self.assertNotIn('new-portal-secret', result.stdout)
        self.assertNotIn('new-airflow-secret', result.stdout)

    def test_root_lists_every_supported_input_and_routes_optional_values(self):
        example = read_env(ROOT / 'identity.env.example')
        self.assertEqual(example.keys(), INPUT_KEYS)
        self.assertFalse(any(example[key] for key in (
            'CORP_OIDC_CLIENT_ID', 'CORP_OIDC_CLIENT_SECRET',
            'DJANGO_DB_HOST', 'DJANGO_DB_NAME', 'DJANGO_DB_USER', 'DJANGO_DB_PASSWORD',
            'OPENWEBUI_API_TOKEN', 'MAIL_API_KEY', 'KNOX_MESSENGER_AUTHORIZATION', 'DRONE_JIRA_TOKEN',
        )))
        apps = read_catalog()['apps']
        for variable, (app, _, overrides) in APP_OVERRIDES.items():
            with self.subTest(variable=variable):
                base_path = Path(inputs(apps[app], {})[variable])
                self.assertFalse(overrides.values() - read_env(base_path).keys())
        sdwts = self.identity.with_name('sdwts.csv')
        users = self.identity.with_name('users.csv')
        sdwts.touch()
        users.touch()
        self.identity.write_text(self.identity.read_text() + 'postgres-password=new-db-fixture\n'
                                 'bootstrap-admin-password=\nIAM_STORAGE_NODE=worker-b\n'
                                 'KEYCLOAK_SDWTS_CSV=sdwts.csv\nKEYCLOAK_USERS_CSV=users.csv\n'
                                 'REGISTRY_USER=publisher\nREGISTRY_PASSWORD=publish-credential\n')
        arguments = prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(arguments['KEYCLOAK_SDWTS_CSV'], sdwts)
        self.assertEqual(arguments['KEYCLOAK_USERS_CSV'], users)
        self.assertEqual(read_env(arguments['KEYCLOAK_ENV'])['postgres-password'], 'new-db-fixture')
        self.assertEqual(read_env(arguments['KEYCLOAK_ENV'])['bootstrap-admin-password'], 'admin-fixture')
        self.assertEqual(read_env(arguments['IAM_ENV'])['IAM_STORAGE_NODE'], 'worker-b')
        account = arguments['REGISTRY_PUSH_ENV']
        self.assertEqual(stat.S_IMODE(account.stat().st_mode), 0o600)
        self.assertEqual(read_env(account), {'REGISTRY_USER': 'publisher', 'REGISTRY_PASSWORD': 'publish-credential'})

    def test_optional_admin_override_and_invalid_input_keep_previous_files(self):
        required = 'CORP_OIDC_CLIENT_ID=another-id\nCORP_OIDC_CLIENT_SECRET=another-secret\n'
        self.identity.write_text(required)
        arguments = prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(read_env(arguments['IAM_ENV'])['IAM_PLATFORM_ADMIN_USERNAMES'], '99')
        self.assertEqual(arguments['IAM_ENV'], self.iam)
        self.identity.write_text(required + 'IAM_PLATFORM_ADMIN_USERNAMES=\n')
        arguments = prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(read_env(arguments['IAM_ENV'])['IAM_PLATFORM_ADMIN_USERNAMES'], '')
        previous = [path.read_bytes() for path in arguments.values()]
        self.identity.write_text(required + 'UNSUPPORTED_INPUT=unexpected\n')
        with self.assertRaisesRegex(ValueError, 'identity.env.example'):
            prepare(self.identity, self.keycloak, self.iam)
        self.identity.write_text(required + 'REGISTRY_USER=publisher\n')
        with self.assertRaisesRegex(ValueError, 'REGISTRY_USER·REGISTRY_PASSWORD'):
            prepare(self.identity, self.keycloak, self.iam)
        self.assertEqual(previous, [path.read_bytes() for path in arguments.values()])

    def test_public_input_and_generated_base_are_rejected(self):
        arguments = prepare(self.identity, self.keycloak, self.iam)
        with self.assertRaisesRegex(ValueError, '생성본은 원본으로'):
            prepare(self.identity, arguments['KEYCLOAK_ENV'], self.iam)
        self.identity.chmod(0o644)
        with self.assertRaisesRegex(ValueError, '0600'):
            prepare(self.identity, self.keycloak, self.iam)

    def test_make_routes_portal_db_shared_token_and_other_platform_apps(self):
        parent = self.identity.parent
        bases = {}
        for key in ('PROD_API_ENV_FILE', 'AIRFLOW_ENV', 'MINIO_ENV', 'MONITORING_ENV', 'REGISTRY_ENV', 'FTP_ENV'):
            path = parent / key
            path.write_text('UNCHANGED=existing\n')
            bases[key] = path
        self.identity.write_text(
            'DJANGO_DB_HOST=db.example.test\nDJANGO_DB_NAME=portal\nDJANGO_DB_USER=portal-user\n'
            'DJANGO_DB_PASSWORD=db-secret\nAIRFLOW_TRIGGER_TOKEN=shared-secret\nMINIO_ROOT_USER=minio-user\n'
            'MINIO_ROOT_PASSWORD=minio-secret\nGRAFANA_ADMIN_USER=grafana-user\nGRAFANA_ADMIN_PASSWORD=grafana-secret\n'
            'FTP_USER=ftp-user\nFTP_PASS=ftp-secret\nFTP_NODES=worker-a,worker-b\nFTP_IMAGE=mirror/ftp:v1\n'
            'MONITORING_NODE_NAME=monitor-worker\nREGISTRY_DATA_HOST_PATH=/appdata/registry\nKUBE_CONTEXT=corp\n'
        )
        command = ['make', '-s', 'identity-env-prepare', f'IDENTITY_ENV={self.identity}',
                   f'KEYCLOAK_ENV={self.keycloak}', f'IAM_ENV={self.iam}']
        command.extend(f'{key}={path}' for key, path in bases.items())
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        arguments = dict(line.split('=', 1) for line in result.stdout.splitlines())
        self.assertEqual(arguments['FTP_NODES'], 'worker-a,worker-b')
        self.assertEqual(arguments['KUBE_CONTEXT'], 'corp')
        self.assertEqual(read_env(Path(arguments['PROD_API_ENV_FILE'])), {
            'UNCHANGED': 'existing', 'DJANGO_DB_HOST': 'db.example.test', 'DJANGO_DB_NAME': 'portal',
            'DJANGO_DB_USER': 'portal-user', 'DJANGO_DB_PASSWORD': 'db-secret', 'AIRFLOW_TRIGGER_TOKEN': 'shared-secret',
        })
        for variable, overrides in {
            'AIRFLOW_ENV': {'AIRFLOW_TRIGGER_TOKEN': 'shared-secret'},
            'MINIO_ENV': {'MINIO_ROOT_USER': 'minio-user', 'MINIO_ROOT_PASSWORD': 'minio-secret'},
            'MONITORING_ENV': {'NODE_NAME': 'monitor-worker'},
            'REGISTRY_ENV': {'DATA_HOST_PATH': '/appdata/registry'},
            'FTP_ENV': {'FTP_IMAGE': 'mirror/ftp:v1'},
        }.items():
            self.assertEqual(read_env(Path(arguments[variable])), {'UNCHANGED': 'existing', **overrides})
        for variable, values in {
            'MONITORING_GRAFANA_ENV': {'admin-user': 'grafana-user', 'admin-password': 'grafana-secret'},
            'FTP_CREDENTIAL_FILE': {'FTP_USER': 'ftp-user', 'FTP_PASS': 'ftp-secret'},
        }.items():
            path = Path(arguments[variable])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(read_env(path), values)
        self.assertNotIn('secret', result.stdout)
        self.assertTrue(all(read_env(path) == {'UNCHANGED': 'existing'} for path in bases.values()))
