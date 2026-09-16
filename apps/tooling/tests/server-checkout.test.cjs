const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const root = path.resolve(__dirname, '../../..');

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
  fs.copyFileSync(path.join(root, 'Makefile'), path.join(source, 'Makefile'));
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

for (const app of ['keycloak', 'portal', 'airflow', 'ftp', 'monitoring']) {
  test(`${app} 서버 선택 체크아웃은 local을 제외하고 Kubernetes 준비 상태를 검사한다`, t => {
    const checkout = fixture(t);
    run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', app]);
    assert.equal(fs.existsSync(path.join(checkout, 'local')), false);
    assert.equal(fs.existsSync(path.join(checkout, 'apps')), false);
    for (const other of ['keycloak', 'portal', 'airflow', 'ftp', 'monitoring'].filter(other => other !== app)) {
      assert.equal(fs.existsSync(path.join(checkout, 'deploy', other)), false);
    }
    const chartFile = process.env.AIRFLOW_CHART_FILE || path.join(root, 'deploy/airflow/helm/vendor/airflow-1.22.0.tgz');
    const airflowToolsReady = fs.existsSync(chartFile) && spawnSync('helm', ['version', '--short']).status === 0;
    const monitoringLock = JSON.parse(fs.readFileSync(path.join(root, 'deploy/monitoring/helm/chart.lock.json'), 'utf8'));
    const monitoringChart = process.env.MONITORING_CHART_FILE || path.join(root, `deploy/monitoring/helm/vendor/kube-prometheus-stack-${monitoringLock.version}.tgz`);
    const monitoringToolsReady = fs.existsSync(monitoringChart) && spawnSync('helm', ['version', '--short']).status === 0;
    const result = spawnSync('make', ['server-check', `APP=${app}`], {
      cwd: checkout, encoding: 'utf8',
      env: { ...process.env, AIRFLOW_CHART_FILE: chartFile, MONITORING_CHART_FILE: monitoringChart },
    });
    if (app === 'monitoring' && !monitoringToolsReady) {
      assert.notEqual(result.status, 0);
      assert.match(result.stderr, /Helm (chart|실행 파일) 준비 필요/);
    } else if (app === 'airflow' && !airflowToolsReady) {
      assert.notEqual(result.status, 0);
      // 오프라인 checkout은 차트·Helm을 반입해야 하며 Compose로 대신 통과하지 않는다.
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

test('서버 검사는 미지원 환경과 선택 앱의 누락된 예시를 차단한다', t => {
  const checkout = fixture(t);
  run(checkout, 'bash', ['deploy/shared/scripts/checkout-server.sh', 'portal']);
  const args = ['deploy/shared/scripts/check-server.sh', 'portal'];
  assert.notEqual(spawnSync('bash', [...args, 'local'], { cwd: checkout }).status, 0);
  fs.rmSync(path.join(checkout, 'deploy/portal/env/prod/api.env.example'));
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

for (const app of ['portal', 'airflow', 'keycloak-airflow', 'all', 'keycloak']) {
  test(`${app} 소스 선택은 해당 앱 소스만 추가하고 기본 모드로 복귀한다`, t => {
    const checkout = fixture(t);
    const script = 'deploy/shared/scripts/checkout-server.sh';
    run(checkout, 'bash', [script, app, '--with-source']);
    const names = app === 'all' ? ['portal', 'airflow'] : app === 'keycloak-airflow' ? ['airflow'] : [app];
    for (const name of ['portal', 'airflow']) {
      assert.equal(fs.existsSync(path.join(checkout, 'apps', name)), names.includes(name));
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
