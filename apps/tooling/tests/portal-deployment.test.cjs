const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');

function render(directory) {
  const result = spawnSync('kubectl', ['kustomize', directory], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return yaml.loadAll(result.stdout).filter(Boolean);
}

test('MinIO 초기화는 기존 버킷을 허용하고 버킷 생성 실패를 Job 실패로 전달한다', t => {
  const resources = render('deploy/minio/k8s');
  const job = resources.find(item => item.kind === 'Job' && item.metadata.name === 'minio-init');
  const command = job.spec.template.spec.containers[0].command;
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-minio-init-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  // mc의 외부 명령 계약을 대체해 실제 초기화 셸의 종료·재실행 동작을 확인합니다.
  fs.writeFileSync(path.join(directory, 'mc'), `#!/bin/sh
if [ "$1" = alias ]; then exit 0; fi
case "$MC_SCENARIO" in
  new) exit 0 ;;
  existing)
    case "$*" in *' -p '*|*' --ignore-existing '*) exit 0 ;; esac
    exit 1 ;;
  failure) exit 7 ;;
esac
exit 2
`, { mode: 0o755 });
  for (const scenario of ['new', 'existing', 'failure']) {
    const result = spawnSync(command[0], command.slice(1), {
      cwd: directory, encoding: 'utf8', timeout: 5000,
      env: { ...process.env, PATH: `${directory}${path.delimiter}${process.env.PATH}`,
        MINIO_ROOT_USER: 'fixture', MINIO_ROOT_PASSWORD: 'fixture', MINIO_BUCKETS: 'emails,profile', MC_SCENARIO: scenario },
    });
    if (scenario === 'failure') assert.equal(result.status, 7, result.stderr);
    else assert.equal(result.status, 0, `${scenario}: ${result.stderr}`);
  }
  assert.ok(job.spec.activeDeadlineSeconds > 0 && job.spec.activeDeadlineSeconds <= 600,
    '연결 대기가 끝나지 않아도 Job은 제한 시간 안에 실패해야 합니다.');
});

test('Portal의 로컬·운영 health probe는 HTTPS 강제 전환 없이 handler에 도달한다', () => {
  for (const directory of ['deploy/portal/k8s/overlays/prod', 'local/portal/k8s']) {
    const resources = render(directory);
    for (const name of ['api', 'edge-nginx']) {
      const deployment = resources.find(item => item.kind === 'Deployment' && item.metadata.name === name);
      const container = deployment.spec.template.spec.containers[0];
      for (const type of ['readinessProbe', 'livenessProbe']) {
        const probe = container[type].httpGet;
        assert.equal(probe.path, '/api/v1/health/');
        const headers = Object.fromEntries(probe.httpHeaders.map(item => [item.name.toLowerCase(), item.value]));
        assert.equal(headers.host, 'localhost');
        assert.equal(headers['x-forwarded-proto'], 'https', `${directory}/${name}/${type}`);
      }
    }
  }
});
