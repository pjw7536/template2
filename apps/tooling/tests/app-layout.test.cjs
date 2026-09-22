const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const root = path.resolve(__dirname, '../../..');

function config(file, overrides = {}, options = []) {
  const result = spawnSync('docker', ['compose', ...options, '-f', file, 'config', '--format', 'json'], {
    cwd: root, encoding: 'utf8', timeout: 30000,
    env: {
      ...process.env, ...overrides,
    },
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function mount(service, target) {
  return service.volumes.find(volume => volume.target === target).source;
}


test('Node 프로젝트와 Compose는 루트 파일 없이 독립적으로 관리된다', () => {
  for (const name of ['package.json', 'package-lock.json', 'node_modules', 'docker-compose.yml', 'docker-compose.dev.yml', 'docker-compose.test.yml', 'docker-compose.oidc.yml']) {
    assert.equal(fs.existsSync(path.join(root, name)), false, name);
  }
  for (const folder of ['apps/portal/web', 'apps/tooling']) {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, folder, 'package.json'), 'utf8'));
    assert.equal(manifest.workspaces, undefined);
    assert.ok(fs.existsSync(path.join(root, folder, 'package-lock.json')));
  }
  assert.ok(require.resolve('js-yaml').startsWith(path.join(root, 'apps/tooling/node_modules')));
});

test('Makefile은 로컬 API 검사와 CI에 유지된 Compose 경로를 사용한다', () => {
  for (const [target, file] of [
    ['check-api', 'local/shared/compose/k8s-check.yml'],
    ['test-api', 'local/shared/compose/k8s-check.yml'],
    ['build-ci-api', 'deploy/portal/compose/test.yml'],
    ['test-ci-api', 'deploy/portal/compose/test.yml'],
  ]) {
    const result = spawnSync('make', ['-n', target], { cwd: root, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.ok(result.stdout.includes(`-f ${file}`), target);
  }
});


test('CI API 빌드 context와 테스트 소스 mount가 같은 새 경로를 사용한다', () => {
  const service = config('deploy/portal/compose/test.yml').services['api-test'];
  assert.equal(service.build.context, path.join(root, 'apps/portal/api'));
  assert.equal(mount(service, '/app'), service.build.context);
});

// 보조 Compose 검사에는 실제 클러스터·runtime env가 필요하지 않습니다.
test('Compose 검사는 빈 runtime에서도 DB·API 검사·CI 원본을 렌더링한다', () => {
  const result = spawnSync('bash', ['apps/tooling/agent/check_compose_configs.sh'], {
    cwd: root, encoding: 'utf8', timeout: 30000,
    env: { ...process.env, K8S_API_ENV_FILE: '/not-a-real-runtime/api.env', POSTGRES_PASSWORD: '' },
  });
  assert.equal(result.status, 0, result.stderr);
});

test('로컬 DB와 API 검사 Compose는 같은 kind 연결과 영속 DB 이름을 유지한다', () => {
  const env = { POSTGRES_PASSWORD: 'fixture', PORTAL_DB_PASSWORD: 'fixture', AIRFLOW_DB_PASSWORD: 'fixture', KEYCLOAK_DB_PASSWORD: 'fixture' };
  const db = config('local/shared/compose/k8s-db.yml', env, ['--project-name', 'tailwind-local-db']);
  const api = config('local/shared/compose/k8s-check.yml', {
    ...env, K8S_API_ENV_FILE: path.join(root, 'deploy/portal/env/test/api.env'),
  });
  assert.equal(db.volumes.postgres_data.name, 'tailwind-local-db_postgres_data');
  assert.equal(db.networks.kind.name, api.networks.kind.name);
  assert.equal(db.networks.kind.external, true);
  assert.equal(api.services.api.environment.DJANGO_DB_HOST, 'tailwind-local-db-postgres-1');
  assert.equal(api.services.api.image, 'tailwind-api:k8s-local');
  assert.deepEqual(api.services.api.entrypoint, ['python', 'manage.py']);
});
