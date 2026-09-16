"""Headlamp 배포 입력과 변경 전 차단 조건을 검증한다."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('headlamp_manage', SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class DeploymentTest(unittest.TestCase):
    """외부 명령 실행 전에 잘못된 입력이 거부되는지 확인한다."""

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
            path.write_text('HEADLAMP_REGISTRY=mirror.test:5000/ghcr\nIMAGE_PULL_SECRET=pull-secret')
            self.assertEqual(manage.settings(path)['imagePullSecrets'], [{'name': 'pull-secret'}])

    def test_chart_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.tgz'
            path.write_bytes(b'wrong archive')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                manage.verify_chart(path)

    def test_context_required(self):
        for action in ['deploy', 'ui']:
            result = subprocess.run(['python3', str(SCRIPT), action], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('KUBE_CONTEXT', result.stderr)


if __name__ == '__main__':
    unittest.main()
