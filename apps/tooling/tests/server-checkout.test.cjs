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
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'server-checkout-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const source = path.join(dir, 'source');
  fs.mkdirSync(source);
  // 실제 env·백업은 복사하지 않으며 테스트 전용 저장소에 공개 원본과 가짜 값만 기록합니다.
  fs.cpSync(path.join(root, 'deploy'), path.join(source, 'deploy'), {
    recursive: true,
    filter: file => !file.endsWith('.env') && !file.endsWith('.bak'),
  });
  // 배포 env 경로를 보존하되 credential 값은 테스트 입력으로 대체합니다.
  for (const relative of ['airflow/env/k8s.env', 'airflow/env/build.env', 'monitoring/env/k8s.env',
    'headlamp/env/k8s.env', 'keycloak/env/prod.env', 'portal/env/prod/api.env',
    'portal/env/prod/web.env', 'minio/env/prod.env', 'portal/env/test/api.env']) {
    const input = fs.readFileSync(path.join(root, 'deploy', relative), 'utf8');
    const sanitized = input.split('\n').map(line => {
      const key = line.split('=')[0];
      return !key.startsWith('#') && /password|token|fernet|authorization|secret.key|client.secret|access.key/i.test(key)
        ? `${key}=replace-me` : line;
    }).join('\n');
    fs.writeFileSync(path.join(source, 'deploy', relative), sanitized, { mode: 0o600 });
  }
  fs.copyFileSync(path.join(root, 'Makefile'), path.join(source, 'Makefile'));
  fs.copyFileSync(path.join(root, '.gitignore'), path.join(source, '.gitignore'));
  for (const folder of ['docs', 'apps/portal/api', 'apps/portal/web', 'apps/airflow', 'local']) {
    fs.mkdirSync(path.join(source, folder), { recursive: true });
    fs.writeFileSync(path.join(source, folder, 'fixture.txt'), 'test fixture\n');
  }
  run(source, 'git', ['init', '-q']);
  run(source, 'git', ['add', '.']);
  run(source, 'git', ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture']);
  const checkout = path.join(dir, 'checkout');
  run(dir, 'git', ['clone', '--sparse', '--no-local', source, checkout]);
  run(checkout, 'git', ['sparse-checkout', 'set', '--cone', 'deploy/shared']);
  return checkout;
}

for (const app of appNames) {
  test(`${app} 서버 선택 체크아웃은 local을 제외하고 Kubernetes 준비 상태를 검사한다`, t => {
    const checkout = fixture(t);
    run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', app]);
    assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
    assert.equal(fs.existsSync(path.join(checkout, 'apps')), false);
    assert.equal(fs.existsSync(path.join(checkout, 'docs')), false);
    for (const other of appNames.filter(other => other !== app)) {
      const supporting = (catalog.apps[app].supportPaths || []).some(relative => relative.startsWith(`deploy/${other}/`));
      assert.equal(fs.existsSync(path.join(checkout, 'deploy', other)), supporting);
      if (supporting) assert.equal(fs.existsSync(path.join(checkout, 'deploy', other, 'env')), false);
    }
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
      assert.match(result.stderr, app === 'headlamp'
        ? /Headlamp 실행 실패: .*No such file or directory/
        : /Helm (chart|실행 파일) 준비 필요/);
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

test('Portal 전용 checkout은 Keycloak env·앱 소스 없이 공식 client 등록 명령을 실행한다', t => {
  const checkout = fixture(t);
  run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', 'portal']);
  assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
  assert.equal(fs.existsSync(path.join(checkout, 'apps')), false);
  assert.equal(fs.existsSync(path.join(checkout, 'deploy/keycloak/env')), false);
  assert.equal(run(checkout, 'python3', ['deploy/shared/scripts/app-paths.py', 'portal', '--names']), 'portal\n');
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

test('선택 범위 변경은 수정 파일과 미지원 앱을 보존하고 중단한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  assert.notEqual(spawnSync('bash', [script, 'unknown'], { cwd: checkout }).status, 0);
  fs.appendFileSync(path.join(checkout, 'Makefile'), '\n# 사용자 수정\n');
  const result = spawnSync('bash', [script, 'portal'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /작업 파일 변경/);
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
  assert.ok(fs.readFileSync(path.join(checkout, 'Makefile'), 'utf8').endsWith('# 사용자 수정\n'));
});

test('제외될 앱의 ignored 백업은 선택 전환을 막고 파일과 기존 범위를 보존한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'portal']);
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  const relative = 'deploy/portal/env/prod/api.env.pre-k8s.bak';
  const backup = path.join(checkout, relative);
  fs.writeFileSync(backup, 'fixture-backup\n');
  run(checkout, 'git', ['check-ignore', '-q', relative]);
  assert.equal(run(checkout, 'git', ['status', '--porcelain', '--untracked-files=normal']), '');
  const result = spawnSync('bash', [script, 'airflow'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /ignored/);
  assert.ok(result.stderr.includes(relative));
  assert.equal(fs.readFileSync(backup, 'utf8'), 'fixture-backup\n');
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
  assert.ok(fs.existsSync(path.join(checkout, 'deploy/portal/env/prod/api.env')));
  // 운영자가 저장소 밖에 보존한 뒤 같은 명령으로 다시 진행할 수 있습니다.
  const saved = path.join(path.dirname(checkout), 'saved-backup');
  fs.renameSync(backup, saved);
  run(checkout, 'bash', [script, 'airflow']);
  assert.equal(fs.readFileSync(saved, 'utf8'), 'fixture-backup\n');
  assert.equal(fs.existsSync(path.join(checkout, 'deploy/portal')), false);
});

test('소스의 ignored env는 --with-source 해제 시 보존한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'portal', '--with-source']);
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  const env = path.join(checkout, 'apps/portal/api/.env');
  fs.writeFileSync(env, 'fixture-local-env\n');
  const result = spawnSync('bash', [script, 'portal'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.equal(fs.readFileSync(env, 'utf8'), 'fixture-local-env\n');
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
});

test('선택 경로·공통 경로·root·cone 상위 파일의 ignored 입력은 허용하고 보존한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'portal']);
  const retained = ['.env', 'deploy/ancestor.pem', 'deploy/shared/certs/review.key',
    'deploy/portal/env/prod/api.env.pre-k8s.bak'];
  for (const relative of retained) {
    const file = path.join(checkout, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, `fixture: ${relative}\n`);
    run(checkout, 'git', ['check-ignore', '-q', relative]);
  }
  run(checkout, 'bash', [script, 'all']);
  for (const relative of retained) {
    assert.equal(fs.readFileSync(path.join(checkout, relative), 'utf8'), `fixture: ${relative}\n`);
  }
  assert.ok(fs.existsSync(path.join(checkout, 'deploy/airflow')));
  assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
});

test('서버 범위에서 제외할 docs의 ignored 파일은 전환 전에 보존한다', t => {
  const checkout = fixture(t);
  run(checkout, 'git', ['sparse-checkout', 'set', '--cone', 'deploy/shared', 'docs']);
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  const relative = 'docs/review.pem';
  const certificate = path.join(checkout, relative);
  fs.writeFileSync(certificate, 'fixture-certificate\n');
  run(checkout, 'git', ['check-ignore', '-q', relative]);
  const result = spawnSync('bash', ['deploy/shared/scripts/checkout-server.sh', 'platform'], {
    cwd: checkout, encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  assert.ok(result.stderr.includes(relative));
  assert.equal(fs.readFileSync(certificate, 'utf8'), 'fixture-certificate\n');
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
});

test('공백·줄바꿈·한글이 있는 ignored 백업 이름도 보존한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'portal']);
  const relative = 'deploy/portal/env/prod/review \n한글.pre-k8s.bak';
  const backup = path.join(checkout, relative);
  fs.writeFileSync(backup, 'fixture-special-path\n');
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  const result = spawnSync('bash', [script, 'airflow'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.equal(fs.readFileSync(backup, 'utf8'), 'fixture-special-path\n');
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
});

test('제외될 경로의 ignored 심볼릭 링크도 삭제하지 않는다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'portal']);
  const target = path.join(path.dirname(checkout), 'external-private-key');
  fs.writeFileSync(target, 'fixture-private-key\n');
  const link = path.join(checkout, 'deploy/portal/env/prod/review.key');
  fs.symlinkSync(target, link);
  const result = spawnSync('bash', [script, 'airflow'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.equal(fs.readlinkSync(link), target);
  assert.equal(fs.readFileSync(target, 'utf8'), 'fixture-private-key\n');
});

test('ignored 중첩 Git 디렉터리는 root 파일로 잘못 허용하지 않는다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  const nested = path.join(checkout, 'vendor');
  fs.mkdirSync(nested);
  run(nested, 'git', ['init', '-q']);
  const file = path.join(nested, 'backup.txt');
  fs.writeFileSync(file, 'fixture-nested-backup\n');
  const before = run(checkout, 'git', ['sparse-checkout', 'list']);
  const result = spawnSync('bash', [script, 'airflow'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.ok(result.stderr.includes('vendor/'));
  assert.equal(fs.readFileSync(file, 'utf8'), 'fixture-nested-backup\n');
  assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
});

test('서버 검사는 미지원 환경과 선택 앱의 누락된 env를 차단한다', t => {
  const checkout = fixture(t);
  run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', 'portal']);
  const args = ['deploy/shared/scripts/check-server.sh', 'portal'];
  assert.notEqual(spawnSync('bash', [...args, 'local'], { cwd: checkout }).status, 0);
  fs.rmSync(path.join(checkout, 'deploy/portal/env/prod/api.env'));
  const result = spawnSync('bash', [...args, 'prod'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /설정 파일이 없습니다/);
});

test('Keycloak·Airflow 선택은 두 앱과 공용 ingress만 포함한다', t => {
  const checkout = fixture(t);
  run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', 'keycloak-airflow']);
  for (const folder of ['deploy/keycloak', 'deploy/airflow', 'deploy/shared/ingress']) {
    assert.ok(fs.existsSync(path.join(checkout, folder)), folder);
  }
  for (const folder of ['local', 'deploy/portal', 'deploy/monitoring', 'apps']) {
    assert.equal(fs.existsSync(path.join(checkout, folder)), false, folder);
  }
  run(checkout, 'kubectl', ['kustomize', 'deploy/keycloak/k8s']);
  const result = spawnSync('make', ['server-up'], { cwd: checkout, encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /--context/);
});

test('platform은 Portal 없이 준비하고 all 확장 시 기반 앱과 인증서를 유지한다', t => {
  const checkout = fixture(t);
  const script = 'deploy/shared/scripts/checkout-server.sh';
  run(checkout, 'bash', [script, 'platform']);
  const expected = appNames.filter(app => app !== 'portal');
  assert.deepEqual(run(checkout, 'python3', ['deploy/shared/scripts/app-paths.py', 'platform', '--names'])
    .trim().split('\n'), expected);
  for (const app of expected) assert.ok(fs.existsSync(path.join(checkout, 'deploy', app)));
  for (const folder of ['deploy/portal', 'apps', 'local', 'docs']) {
    assert.equal(fs.existsSync(path.join(checkout, folder)), false, folder);
  }
  const certificate = path.join(checkout, 'deploy/shared/certs/platform-review.pem');
  fs.writeFileSync(certificate, 'fixture-platform-certificate\n');
  run(checkout, 'git', ['check-ignore', '-q', 'deploy/shared/certs/platform-review.pem']);
  run(checkout, 'bash', [script, 'all']);
  for (const app of appNames) assert.ok(fs.existsSync(path.join(checkout, 'deploy', app)));
  assert.equal(fs.readFileSync(certificate, 'utf8'), 'fixture-platform-certificate\n');
  for (const folder of ['apps', 'local', 'docs']) {
    assert.equal(fs.existsSync(path.join(checkout, folder)), false, folder);
  }
});

test('서버 그룹 검사는 카탈로그에 추가한 그룹의 앱만 실행한다', t => {
  const checkout = fixture(t);
  run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', 'platform']);
  const catalogFile = path.join(checkout, 'deploy/shared/apps.json');
  const selectedCatalog = JSON.parse(fs.readFileSync(catalogFile, 'utf8'));
  selectedCatalog.groups['custom-platform'] = ['keycloak', 'ftp'];
  fs.writeFileSync(catalogFile, JSON.stringify(selectedCatalog));
  const output = run(checkout, 'make', ['server-check', 'APP=custom-platform']);
  assert.match(output, /서버 원본 검사 통과: keycloak\/prod/);
  assert.match(output, /서버 원본 검사 통과: ftp\/prod/);
  assert.doesNotMatch(output, /portal\/prod/);
});

for (const app of [...appNames, ...Object.keys(catalog.groups)]) {
  test(`${app} 소스 선택은 해당 앱 소스만 추가하고 기본 모드로 복귀한다`, t => {
    const checkout = fixture(t);
    const script = 'deploy/shared/scripts/checkout-server.sh';
    run(checkout, 'bash', [script, app, '--with-source']);
    const selected = catalog.groups[app] || [app];
    const sources = selected.flatMap(name => catalog.apps[name].sourcePaths);
    for (const source of Object.values(catalog.apps).flatMap(entry => entry.sourcePaths)) {
      assert.equal(fs.existsSync(path.join(checkout, source)), sources.includes(source));
    }
    assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
    const before = run(checkout, 'git', ['sparse-checkout', 'list']);
    assert.notEqual(spawnSync('bash', [script, app, '--invalid'], { cwd: checkout }).status, 0);
    assert.notEqual(spawnSync('bash', [script, app, '--names'], { cwd: checkout }).status, 0);
    assert.equal(run(checkout, 'git', ['sparse-checkout', 'list']), before);
    run(checkout, 'bash', [script, app]);
    assert.equal(fs.existsSync(path.join(checkout, 'apps')), false);
  });
}
