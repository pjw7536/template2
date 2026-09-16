const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

test('Monitoring의 저장소·미러·중복 Operator 배포 차단을 검사한다', () => {
  const result = spawnSync('python3', ['-m', 'unittest', 'discover', '-s', 'deploy/monitoring/tests', '-v'], {
    cwd: path.resolve(__dirname, '../../..'), encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
