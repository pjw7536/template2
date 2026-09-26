"""OIDC 배포 입력과 비밀값 격리·CA 마운트를 검증한다."""

import base64
import importlib.util
from pathlib import Path
import unittest
from test_manage import deploy, settings


class OidcDeploymentTests(unittest.TestCase):
    def values(self):
        result = settings()
        result.update(AIRFLOW_AUTH_MODE='keycloak', AIRFLOW_OIDC_ISSUER='https://sso.test/realms/main',
                      AIRFLOW_OIDC_CLIENT_SECRET='unique-client-secret-0123456789',
                      AIRFLOW_WEBSERVER_BASE_URL='https://airflow.test/airflow')
        return result

    def test_https_required_and_local_exception_is_explicit(self):
        values = self.values()
        deploy.validate(values)
        values['AIRFLOW_OIDC_ISSUER'] = 'http://localhost:8180/realms/portal'
        with self.assertRaises(ValueError):
            deploy.validate(values)
        values['AIRFLOW_OIDC_ALLOW_HTTP'] = 'true'
        with self.assertRaises(ValueError):
            deploy.validate(values)
        values['AIRFLOW_WEBSERVER_BASE_URL'] = 'http://localhost:8080/airflow'
        deploy.validate(values)

    def test_secret_only_in_secret_manifest(self):
        values = self.values()
        secret = values['AIRFLOW_OIDC_CLIENT_SECRET']
        self.assertNotIn(secret, str(deploy.helm_values(values)))
        runtime = next(item for item in deploy.secret_manifest(values)['items'] if item['metadata']['name'] == 'airflow-runtime')
        self.assertEqual(base64.b64decode(runtime['data']['AIRFLOW_OIDC_CLIENT_SECRET']).decode(), secret)

    def test_ca_mount_preserves_odbc(self):
        values = self.values()
        values.update(AIRFLOW_OIDC_CA_CONFIGMAP='airflow-oidc-ca', AIRFLOW_OIDC_CA_BUNDLE='/etc/airflow/oidc-ca/ca.crt')
        deploy.validate(values)
        mounts = deploy.helm_values(values)['volumeMounts']
        self.assertEqual({m['name'] for m in mounts}, {'odbc', 'oidc-ca'})
        self.assertTrue(all(m['readOnly'] for m in mounts))
        values['AIRFLOW_OIDC_CA_CONFIGMAP'] = ''
        with self.assertRaises(ValueError):
            deploy.validate(values)

    def test_client_is_web_only_and_uses_exact_callback(self):
        source = Path(__file__).resolve().parents[1] / 'k8s/jobs/keycloak-client/setup_client.py'
        spec = importlib.util.spec_from_file_location('client_setup', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        client = module.client_definition(self.values())
        self.assertEqual(client['redirectUris'], ['https://airflow.test/airflow/oauth-authorized/keycloak'])
        self.assertEqual(client['attributes']['pkce.code.challenge.method'], 'S256')
        self.assertFalse(client['directAccessGrantsEnabled'])
        self.assertFalse(client['serviceAccountsEnabled'])
        self.assertFalse(client['fullScopeAllowed'])


class ClientRegistrationTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock
        source = Path(__file__).resolve().parents[1] / 'k8s/jobs/keycloak-client/setup_client.py'
        spec = importlib.util.spec_from_file_location('client_setup', source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.values = OidcDeploymentTests().values()
        self.admin = Mock(root='/admin/realms/main')
        self.calls = []
        self.client = {'id': 'client-uuid', 'clientId': 'airflow', 'attributes': {'existing': 'keep'}, 'secret': 'masked-value'}
        self.roles = [{'id': name, 'name': name} for name in ('Viewer', 'User', 'Admin')]

    def respond(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == 'GET':
            if '/clients?' in path:
                return [self.client]
            if path.endswith('/client-secret'):
                return {'value': self.values['AIRFLOW_OIDC_CLIENT_SECRET']}
            if path.endswith('/roles'):
                return self.roles
            if path.endswith('/protocol-mappers/models'):
                return [{'id': 'mapper-uuid', 'name': 'airflow-client-roles'}]
        return None

    def test_repeat_preserves_secret_attributes_and_user_assignments(self):
        self.admin.request.side_effect = self.respond
        for _ in range(2):
            self.module.configure(self.admin, self.values)
        self.assertFalse(any(method == 'DELETE' or '/users' in path for method, path, _ in self.calls))
        self.assertFalse(any(method != 'GET' and path.endswith('/client-secret') for method, path, _ in self.calls))
        updates = [payload for method, path, payload in self.calls if method == 'PUT' and path.endswith('/clients/client-uuid')]
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0]['attributes']['existing'], 'keep')
        self.assertNotIn('secret', updates[0])
        self.assertTrue(any(method == 'PUT' and path.endswith('/mapper-uuid') for method, path, _ in self.calls))

    def test_secret_mismatch_stops_before_mutation(self):
        def respond(method, path, payload=None):
            if path.endswith('/client-secret'):
                self.calls.append((method, path, payload))
                return {'value': 'existing-different-secret'}
            return self.respond(method, path, payload)
        self.admin.request.side_effect = respond
        with self.assertRaisesRegex(ValueError, 'secret'):
            self.module.configure(self.admin, self.values)
        self.assertTrue(all(method == 'GET' for method, _, _ in self.calls))
