"""로컬 Secret 갱신에서 폐기된 인증 설정이 남지 않는지 검증합니다."""

import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[3] / 'local/shared/scripts'
with patch.object(sys, 'path', [str(SCRIPTS), *sys.path]):
    SPEC = importlib.util.spec_from_file_location('local_runtime', SCRIPTS / 'k8s.py')
    runtime = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(runtime)


class SecretTests(unittest.TestCase):
    def test_update_replaces_old_keys_without_deleting_secret(self):
        state = {'ADFS_AUTH_URL': 'b2xk', 'OIDC_CLIENT_SECRET': 'b2xk'}
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            if 'get' in args:
                return 'secret/api-env'
            self.assertIn('patch', args)
            self.assertNotIn('private-value', ' '.join(args))
            self.assertTrue(kwargs['sensitive'])
            for operation in json.loads(kwargs['data']):
                self.assertEqual(operation['path'], '/data')
                self.assertEqual(operation['op'], 'add')
                state.clear()
                state.update(operation['value'])
            return ''

        with patch.object(runtime, 'run', side_effect=run):
            runtime.secret('tailwind-local', 'api-env', {'OIDC_CLIENT_SECRET': 'private-value'})
        self.assertNotIn('ADFS_AUTH_URL', state)
        self.assertEqual(base64.b64decode(state['OIDC_CLIENT_SECRET']).decode(), 'private-value')
        self.assertEqual(len(calls), 2)

    def test_first_start_creates_secret(self):
        with patch.object(runtime, 'run', return_value=''), patch.object(runtime, 'apply') as apply:
            runtime.secret('tailwind-local', 'api-env', {'OIDC_CLIENT_ID': 'portal'})
        items = apply.call_args.args[0]
        self.assertEqual(items[0]['metadata']['name'], 'api-env')
        self.assertEqual(base64.b64decode(items[0]['data']['OIDC_CLIENT_ID']), b'portal')
        self.assertTrue(apply.call_args.kwargs['sensitive'])
