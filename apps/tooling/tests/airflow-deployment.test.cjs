const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

test('Airflow 배포의 설정·Secret·스토리지·Helm 순서 회귀 검사', () => {
  const result = spawnSync('python3', ['-m', 'unittest', 'discover', '-s', 'deploy/airflow/tests', '-v'], {
    cwd: path.resolve(__dirname, '../../..'), encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
