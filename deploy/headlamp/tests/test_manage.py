"""Headlamp 배포 입력과 변경 전 차단 조건을 검증한다."""

import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('headlamp_manage', SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


OIDC_ENV = ('\nHEADLAMP_HOST=ui.example.test\nHEADLAMP_TLS_SECRET=headlamp-tls'
            '\nHEADLAMP_OIDC_ISSUER_URL=https://sso.example.test/realms/etch'
            '\nHEADLAMP_OIDC_CLIENT_ID=headlamp\nHEADLAMP_OIDC_SECRET=headlamp-oidc')


class DeploymentTest(unittest.TestCase):
    """외부 명령 실행 전에 잘못된 입력이 거부되는지 확인한다."""

    def test_oidc_provider_checks_real_contract_without_credentials(self):
        values = manage.settings(manage.APP / 'env/k8s.env')
        issuer = next(item['value'] for item in values['env'] if item['name'] == 'OIDC_ISSUER_URL')
        discovery = {
            'issuer': issuer, 'response_types_supported': ['code'],
            'id_token_signing_alg_values_supported': ['RS256'],
            'code_challenge_methods_supported': ['S256'],
            **{key: f'{issuer}/protocol/openid-connect/{suffix}' for key, suffix in
               [('authorization_endpoint', 'auth'), ('token_endpoint', 'token'), ('jwks_uri', 'certs')]},
        }
        jwks = {'keys': [{'kid': 'test', 'kty': 'RSA', 'n': 'modulus', 'e': 'AQAB'}]}
        for change, key_data, expected in [
                ({}, jwks, None), ({'issuer': issuer + '/'}, jwks, 'issuer'),
                ({'token_endpoint': 'http://internal/token'}, jwks, 'token_endpoint'),
                ({'code_challenge_methods_supported': []}, jwks, 'S256'),
                ({'id_token_signing_alg_values_supported': ['HS256']}, jwks, 'RS256'),
                ({}, {'keys': []}, '공개키'), ({}, {'keys': ['bad']}, '공개키')]:
            with self.subTest(change=change, keys=key_data), \
                    patch.object(manage.ssl, 'create_default_context') as tls, \
                    patch.object(manage.urllib.request.OpenerDirector, 'open') as request, patch('builtins.print'):
                responses = []
                for url, payload in [(issuer + '/.well-known/openid-configuration', discovery | change),
                                     (discovery['jwks_uri'], key_data)]:
                    response = MagicMock()
                    response.__enter__.return_value = response
                    response.geturl.return_value = url
                    response.read.return_value = json.dumps(payload).encode()
                    responses.append(response)
                request.side_effect = responses
                if expected:
                    with self.assertRaisesRegex(ValueError, expected):
                        manage.check_oidc_provider(values, Path('/test/ca.pem'))
                else:
                    manage.check_oidc_provider(values, Path('/test/ca.pem'))
                    self.assertEqual(request.call_count, 2)
                    self.assertEqual(request.call_args.kwargs['timeout'], 15)
                tls.assert_called_once_with(cafile='/test/ca.pem')

    def test_oidc_provider_requires_local_ca_and_propagates_tls_failure(self):
        values = manage.settings(manage.APP / 'env/k8s.env')
        with patch.object(manage.urllib.request.OpenerDirector, 'open') as request:
            with self.assertRaisesRegex(ValueError, 'HEADLAMP_OIDC_CA_FILE'):
                manage.check_oidc_provider(values)
            request.assert_not_called()
        with patch.object(manage.ssl, 'create_default_context'), \
                patch.object(manage.urllib.request.OpenerDirector, 'open', side_effect=manage.ssl.SSLError('untrusted')):
            with self.assertRaises(manage.ssl.SSLError):
                manage.check_oidc_provider(values, Path('/test/ca.pem'))

    def test_default_profile_is_valid_production_input(self):
        values = manage.settings(manage.APP / 'env/k8s.env')
        env = {entry['name']: entry['value'] for entry in values['env']}
        self.assertEqual(env['OIDC_ISSUER_URL'], 'https://etch-sso.samsungds.net/realms/etch')
        self.assertEqual(values['volumes'][0]['configMap']['name'], 'headlamp-oidc-ca')
        self.assertNotIn('OIDC_CLIENT_SECRET', env)

    def test_setup_env_follows_custom_names_without_chart_or_cluster(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            path.write_text(('HEADLAMP_REGISTRY=mirror.test' + OIDC_ENV).replace(
                'HEADLAMP_OIDC_SECRET=headlamp-oidc', 'HEADLAMP_OIDC_SECRET=custom-oidc'))
            result = subprocess.run(['python3', str(SCRIPT), 'setup-env', '--env', str(path)],
                                    capture_output=True, text=True, check=True)
            exported = dict(line.split('=', 1) for line in result.stdout.splitlines())
            self.assertEqual(exported['HEADLAMP_OIDC_SECRET'], 'custom-oidc')
            self.assertEqual(exported['HEADLAMP_OIDC_CA_CONFIGMAP'], '')
            self.assertEqual(exported['HEADLAMP_SSO_HOST'], 'sso.example.test')
            self.assertEqual(exported['HEADLAMP_CALLBACK_URL'], 'https://ui.example.test/headlamp/oidc-callback')
            self.assertNotIn('OIDC_CLIENT_SECRET', exported)

    def test_env_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            for value in ['HEADLAMP_REGISTRY=https://mirror.test',
                          'HEADLAMP_REGISTRY=registry.example.invalid/ghcr',
                          'HEADLAMP_REGISTRY=mirror.test\nHEADLAMP_REGISTRY=other.test',
                          'HEADLAMP_REGISTRY=mirror.test\nUNKNOWN=value']:
                path.write_text(value)
                with self.assertRaises(ValueError):
                    manage.settings(path)
            path.write_text('HEADLAMP_REGISTRY=mirror.test:5000/ghcr\nIMAGE_PULL_SECRET=pull-secret' + OIDC_ENV)
            self.assertEqual(manage.settings(path)['imagePullSecrets'], [{'name': 'pull-secret'}])

    def test_chart_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.tgz'
            path.write_bytes(b'wrong archive')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                manage.verify_chart(path)

    def test_oidc_required_and_secret_not_rendered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            valid = 'HEADLAMP_REGISTRY=mirror.test' + OIDC_ENV
            for old, new in [('https://sso.example.test', 'http://sso.example.test'),
                             ('https://sso.example.test', 'https://user:password@sso.example.test'),
                             ('/realms/etch', '/realms/etch?query=1'),
                             ('/realms/etch', '/realms/etch/'),
                             ('HEADLAMP_OIDC_CLIENT_ID=headlamp', 'HEADLAMP_OIDC_CLIENT_ID='),
                             ('HEADLAMP_OIDC_SECRET=headlamp-oidc', 'HEADLAMP_OIDC_SECRET=INVALID'),
                             ('HEADLAMP_HOST=ui.example.test', 'HEADLAMP_HOST=')]:
                path.write_text(valid.replace(old, new))
                with self.subTest(new=new), self.assertRaises(ValueError):
                    manage.settings(path)
            path.write_text(valid + '\nHEADLAMP_OIDC_CLIENT_SECRET=must-not-accept')
            with self.assertRaises(ValueError):
                manage.settings(path)
            path.write_text(valid + '\nHEADLAMP_OIDC_CA_CONFIGMAP=headlamp-ca')
            values = manage.settings(path)
            env = {item['name']: item['value'] for item in values['env']}
            self.assertEqual(env['OIDC_CALLBACK_URL'], 'https://ui.example.test/headlamp/oidc-callback')
            self.assertEqual(env['SSL_CERT_FILE'], '/etc/headlamp-ca/ca.crt')
            self.assertEqual(env['OIDC_USE_ACCESS_TOKEN'], 'false')
            self.assertNotIn('OIDC_CLIENT_SECRET', env)
            self.assertEqual(values['config']['oidc']['externalSecret']['name'], 'headlamp-oidc')
            client = manage.oidc_client(values)
            self.assertEqual(client['redirectUris'], [env['OIDC_CALLBACK_URL']])
            self.assertFalse(client['publicClient'])
            self.assertFalse(client['directAccessGrantsEnabled'])
            self.assertEqual(client['attributes']['id.token.signed.response.alg'], 'RS256')
            self.assertEqual(client['protocolMappers'][0]['config']['full.path'], 'true')
            self.assertNotIn('secret', client)

    def test_oidc_resource_validation(self):
        values = {'config': {'oidc': {'externalSecret': {'name': 'headlamp-oidc'}}}}
        for summary in ['', 'OIDC_CLIENT_SECRET=0', 'OIDC_CLIENT_SECRET=20 UNEXPECTED=4']:
            with self.subTest(summary=summary), patch.object(manage, 'run', return_value=
                    subprocess.CompletedProcess([], 0, summary)):
                with self.assertRaises(ValueError):
                    manage.check_oidc_resources('prod', values)
        values['volumes'] = [{'configMap': {'name': 'headlamp-ca'}}]
        for length in ['0', '1024']:
            with patch.object(manage, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0, 'OIDC_CLIENT_SECRET=20'),
                    subprocess.CompletedProcess([], 0, length)]) as run:
                if length == '0':
                    with self.assertRaises(ValueError):
                        manage.check_oidc_resources('prod', values)
                else:
                    manage.check_oidc_resources('prod', values)
                self.assertEqual(run.call_count, 2)

    def test_ui_prints_sso_url_without_minting_token(self):
        deployment = {'spec': {'template': {'spec': {'containers': [{'env': [
            {'name': 'OIDC_CALLBACK_URL', 'value': 'https://ui.example.test/headlamp/oidc-callback'}]}]}}}}
        with patch('sys.argv', ['manage.py', 'ui', '--context', 'prod']), patch.object(manage, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, ''), subprocess.CompletedProcess([], 0, json.dumps(deployment))
        ]) as run, patch('builtins.print') as output:
            manage.main()
        self.assertEqual(run.call_count, 2)
        self.assertIn('https://ui.example.test/headlamp/', output.call_args.args[0])

    def test_missing_oidc_secret_prevents_helm_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            path.write_text('HEADLAMP_REGISTRY=mirror.test' + OIDC_ENV)
            with patch('sys.argv', ['manage.py', 'deploy', '--context', 'prod', '--env', str(path)]), \
                    patch.object(manage, 'verify_chart'), \
                    patch.object(manage, 'run', side_effect=[
                        subprocess.CompletedProcess([], 0, 'rendered'),
                        subprocess.CalledProcessError(1, ['kubectl'], stderr='Secret not found'),
                    ]) as run, patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    manage.main()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0][1], 'template')
            self.assertIn('secret', run.call_args_list[1].args[0])

    def test_https_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            for extra in ['HEADLAMP_HOST=etch.example.test', 'HEADLAMP_TLS_SECRET=headlamp-tls',
                          'HEADLAMP_HOST=https://etch.example.test\nHEADLAMP_TLS_SECRET=headlamp-tls']:
                path.write_text('HEADLAMP_REGISTRY=mirror.test\n' + extra)
                with self.assertRaises(ValueError):
                    manage.settings(path)
            path.write_text('HEADLAMP_REGISTRY=mirror.test' + OIDC_ENV)
            values = manage.settings(path)
            self.assertEqual(values['config']['baseURL'], '/headlamp')
            self.assertEqual(values['ingress']['tls'][0]['secretName'], 'headlamp-tls')

    def test_ingress_preserves_live_placement_and_namespaces(self):
        current = {'metadata': {'namespace': 'etch-sso', 'resourceVersion': '12'}, 'spec': {
            'replicas': 2, 'template': {'spec': {'serviceAccountName': 'traefik',
            'affinity': {'existing': 'placement'}, 'containers': [{'name': 'traefik', 'image': 'keep:1',
            'args': ['--providers.kubernetesingress=true', '--providers.kubernetesingress.namespaces=etch-sso,airflow',
                     '--entrypoints.websecure.address=:8443']}]}}}}
        original = copy.deepcopy(current)
        values = {'ingress': {'tls': [{'secretName': 'headlamp-tls'}]}}
        for watch_all in (False, True):
            if watch_all:
                current['spec']['template']['spec']['containers'][0]['args'].pop(1)
            with patch.object(manage, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, 'kubernetes.io/tls tls.crt tls.key'),
                subprocess.CompletedProcess([], 0, json.dumps(current)),
            ]):
                access, changes = manage.ingress_plan('prod', values)
            self.assertEqual(changes[0]['op'], 'test')
            if watch_all:
                self.assertEqual(len(changes), 1)
            else:
                self.assertEqual(changes[1]['path'], '/spec/template/spec/containers/0/args')
                self.assertIn('--providers.kubernetesingress.namespaces=etch-sso,airflow,headlamp', changes[1]['value'])
                self.assertEqual(current, original)
            self.assertTrue(all(x['metadata']['namespace'] == 'headlamp' for x in access['items']))
            self.assertEqual(access['items'][1]['subjects'][0]['namespace'], 'etch-sso')

    def test_invalid_tls_stops_before_controller_access(self):
        with patch.object(manage, 'run', return_value=subprocess.CompletedProcess([], 0, 'Opaque tls.crt tls.key')) as run:
            with self.assertRaisesRegex(ValueError, 'TLS Secret'):
                manage.ingress_plan('prod', {'ingress': {'tls': [{'secretName': 'headlamp-tls'}]}})
            self.assertEqual(run.call_count, 1)

    def test_rbac_failure_prevents_controller_patch(self):
        with patch.object(manage, 'run', side_effect=subprocess.CalledProcessError(1, ['kubectl'])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                manage.connect_ingress('prod', {'items': []}, [{'op': 'test'}, {'op': 'replace'}])
            self.assertEqual(run.call_count, 1)
            self.assertIn('apply', run.call_args.args[0])

    def test_context_required(self):
        for action in ['deploy', 'ui']:
            result = subprocess.run(['python3', str(SCRIPT), action], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('KUBE_CONTEXT', result.stderr)


if __name__ == '__main__':
    unittest.main()
