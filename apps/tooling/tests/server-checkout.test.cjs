const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const root = path.resolve(__dirname, '../../..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'deploy/shared/apps.json'), 'utf8'));
const appNames = Object.keys(catalog.apps);

function run(cwd, command, args) {
  const result = spawnSync(command, args, { cwd, encoding: 'utf8', timeout: 30000 });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout;
}

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'server-boundary-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const checkout = path.join(dir, 'checkout');
  fs.mkdirSync(checkout);
  // 서버 도구가 local·앱 소스·docs 없이 동작하는지 보려고 deploy와 Makefile만 복사합니다.
  // 실제 env·백업은 복사하지 않으며 공개 원본과 가짜 값만 기록합니다.
  fs.cpSync(path.join(root, 'deploy'), path.join(checkout, 'deploy'), {
    recursive: true,
    filter: file => !file.endsWith('.env') && !file.endsWith('.bak') && !file.includes('__pycache__'),
  });
  // 배포 env 경로를 보존하되 credential 값은 테스트 입력으로 대체합니다.
  for (const relative of ['airflow/env/k8s.env', 'airflow/env/build.env', 'monitoring/env/k8s.env',
    'headlamp/env/k8s.env', 'keycloak/env/prod.env', 'portal/env/prod/api.env',
    'portal/env/prod/web.env', 'minio/env/prod.env', 'portal/env/test/api.env', 'ftp/env/prod.env']) {
    const input = fs.readFileSync(path.join(root, 'deploy', relative), 'utf8');
    const sanitized = input.split('\n').map(line => {
      const key = line.split('=')[0];
      return !key.startsWith('#') && /password|token|fernet|authorization|secret.key|client.secret|access.key|mail.api.key/i.test(key)
        ? `${key}=replace-me` : line;
    }).join('\n');
    fs.writeFileSync(path.join(checkout, 'deploy', relative), sanitized, { mode: 0o600 });
  }
  fs.copyFileSync(path.join(root, 'Makefile'), path.join(checkout, 'Makefile'));
  return checkout;
}

for (const app of appNames) {
  test(`${app} 서버 검사는 local·앱 소스·docs 없이 Kubernetes 준비 상태를 검사한다`, t => {
    const checkout = fixture(t);
    for (const folder of ['local', 'apps', 'docs']) assert.equal(fs.existsSync(path.join(checkout, folder)), false);
    const chartEnv = {};
    let toolsReady = true;
    if (['airflow', 'monitoring', 'headlamp'].includes(app)) {
      const lock = JSON.parse(fs.readFileSync(path.join(root, `deploy/${app}/helm/chart.lock.json`), 'utf8'));
      const key = `${app.toUpperCase()}_CHART_FILE`;
      chartEnv[key] = process.env[key] || path.join(root, `deploy/${app}/helm/vendor/${lock.name}-${lock.version}.tgz`);
      const helm = app === 'headlamp' ? process.env.HELM_BIN || 'helm' : 'helm';
      toolsReady = fs.existsSync(chartEnv[key]) && spawnSync(helm, ['version', '--short']).status === 0;
    }
    const result = spawnSync('make', ['server-check', `APP=${app}`], {
      cwd: checkout, encoding: 'utf8',
      env: { ...process.env, ...chartEnv },
    });
    if (!toolsReady) {
      assert.notEqual(result.status, 0);
      // 오프라인 checkout은 차트·Helm을 반입해야 하며 Compose로 대신 통과하지 않습니다.
      assert.match(result.stderr, /Helm (chart|실행 파일) 준비 필요/);
    } else {
      assert.equal(result.status, 0, result.stderr);
    }
    const oidc = spawnSync('make', ['server-check', `APP=${app}`, 'PROFILE=oidc'], { cwd: checkout, encoding: 'utf8' });
    assert.notEqual(oidc.status, 0);
    assert.match(oidc.stderr, /Kubernetes 정의가 없습니다/);
    if (app === 'keycloak') run(checkout, 'make', ['k8s-export']);
    assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
  });
}

test('Portal client 등록은 Keycloak env·앱 소스 없이 공식 명령으로 실행한다', t => {
  const checkout = fixture(t);
  fs.rmSync(path.join(checkout, 'deploy/keycloak/env'), { recursive: true, force: true });
  assert.equal(fs.existsSync(path.join(checkout, 'apps')), false);
  assert.equal(run(checkout, 'python3', ['deploy/shared/scripts/app-paths.py', 'portal']), 'portal\n');
  run(checkout, 'kubectl', ['kustomize', 'deploy/portal/k8s/jobs/keycloak-client']);

  const directory = path.dirname(checkout);
  const envFile = path.join(directory, 'portal-client.env');
  fs.writeFileSync(envFile, 'OIDC_PROVIDER=keycloak\nOIDC_CLIENT_ID=portal-fixture\n' +
    'OIDC_CLIENT_SECRET=fixture-client-password\nOIDC_ISSUER=https://sso.test/realms/etch\n' +
    'OIDC_REDIRECT_URI=https://portal.test/auth/keycloak/callback/\nFRONTEND_BASE_URL=https://portal.test\n');
  const bin = path.join(directory, 'bin');
  fs.mkdirSync(bin);
  const log = path.join(directory, 'kubectl.jsonl');
  // 클러스터 호출만 대체하고 실제 Makefile·env 검사·등록 도구 전체를 실행합니다.
  fs.writeFileSync(path.join(bin, 'kubectl'), `#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
event = {'args': args}
if 'create' in args and 'secret' in args:
    source = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--from-env-file='))
    values = dict(line.split('=', 1) for line in Path(source).read_text().splitlines())
    event['clientId'] = values['OIDC_CLIENT_ID']
    event['envKeys'] = sorted(values)
with Path(os.environ['PORTAL_REGISTRATION_LOG']).open('a') as output:
    output.write(json.dumps(event) + '\\n')
if 'create' in args:
    print(json.dumps({'apiVersion': 'v1', 'kind': 'Secret' if 'secret' in args else 'ConfigMap'}))
`, { mode: 0o755 });
  const result = spawnSync('make', ['keycloak-portal-client-setup', 'KUBE_CONTEXT=review-context',
    `KEYCLOAK_PORTAL_ENV=${envFile}`], {
    cwd: checkout, encoding: 'utf8', timeout: 30000,
    env: { ...process.env, PATH: `${bin}${path.delimiter}${process.env.PATH}`, PORTAL_REGISTRATION_LOG: log },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const calls = fs.readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  assert.ok(calls.some(({ args }) => args.includes('job/portal-keycloak-client') && args.includes('wait')));
  for (const { args } of calls.filter(({ args }) => !args.includes('kustomize'))) {
    assert.deepEqual(args.slice(0, 2), ['--context', 'review-context']);
  }
  const input = calls.find(({ args }) => args.includes('create') && args.includes('secret'));
  assert.equal(input.clientId, 'portal-fixture');
  assert.deepEqual(input.envKeys, ['FRONTEND_BASE_URL', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET',
    'OIDC_ISSUER', 'OIDC_REDIRECT_URI']);
  assert.equal(fs.existsSync(path.join(checkout, 'deploy/keycloak/env')), false);
});

test('서버 검사는 미지원 환경과 선택 앱의 누락된 env를 차단한다', t => {
  const checkout = fixture(t);
  const args = ['deploy/shared/scripts/check-server.sh', 'portal'];
  assert.notEqual(spawnSync('bash', [...args, 'local'], { cwd: checkout }).status, 0);
  fs.rmSync(path.join(checkout, 'deploy/portal/env/prod/api.env'));
  const result = spawnSync('bash', [...args, 'prod'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /설정 파일이 없습니다/);
});

test('서버 일괄 배포는 대상 context 없이 실행하지 않는다', t => {
  const checkout = fixture(t);
  run(checkout, 'kubectl', ['kustomize', 'deploy/keycloak/k8s']);
  const result = spawnSync('make', ['server-up'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /--context/);
});

test('platform 그룹은 Portal을 제외한 앱을 검사 대상으로 해석한다', t => {
  const checkout = fixture(t);
  assert.deepEqual(run(checkout, 'python3', ['deploy/shared/scripts/app-paths.py', 'platform']).trim().split('\n'),
    appNames.filter(app => app !== 'portal'));
  assert.notEqual(spawnSync('python3', ['deploy/shared/scripts/app-paths.py', 'unknown'], { cwd: checkout }).status, 0);
});

test('서버 그룹 검사는 카탈로그에 추가한 그룹의 앱만 실행한다', t => {
  const checkout = fixture(t);
  const catalogFile = path.join(checkout, 'deploy/shared/apps.json');
  const selectedCatalog = JSON.parse(fs.readFileSync(catalogFile, 'utf8'));
  selectedCatalog.groups['custom-platform'] = ['keycloak', 'ftp'];
  fs.writeFileSync(catalogFile, JSON.stringify(selectedCatalog));
  const output = run(checkout, 'make', ['server-check', 'APP=custom-platform']);
  assert.match(output, /서버 원본 검사 통과: keycloak\/prod/);
  assert.match(output, /서버 원본 검사 통과: ftp\/prod/);
  assert.doesNotMatch(output, /portal\/prod/);
});
