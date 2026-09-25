const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

const root = path.resolve(__dirname, '../../..');
const fixtures = {
  server: 'postgres-password=db-test\nbootstrap-admin-username=admin\nbootstrap-admin-password=private-marker\nkeycloak-public-url=https://sso.test\n',
  oidc: 'CORP_OIDC_AUTH_URL=https://idp.test/auth\nCORP_OIDC_TOKEN_URL=https://idp.test/token\nCORP_OIDC_ISSUER=https://idp.test\nCORP_OIDC_CLIENT_ID=corp\nCORP_OIDC_CLIENT_SECRET=private-marker\nCORP_OIDC_CLIENT_AUTH_METHOD=client_secret_post\nCORP_OIDC_VALIDATE_SIGNATURE=true\nCORP_OIDC_JWKS_URL=https://idp.test/keys\n',
};

// 운영 credential을 읽지 않는 독립적인 검사 입력입니다.
function portalFixture(component) {
  const common = { OIDC_PROVIDER: 'keycloak', OIDC_CLIENT_ID: 'portal', OIDC_CLIENT_SECRET: 'private-marker',
    OIDC_ISSUER: 'https://sso.test/realms/portal', OIDC_REDIRECT_URI: 'https://portal.test/auth/callback',
    FRONTEND_BASE_URL: 'https://portal.test', ADFS_AUTH_URL: 'https://sso.test/auth',
    ADFS_LOGOUT_URL: 'https://sso.test/logout', OIDC_TOKEN_URL: 'https://sso.test/token', OIDC_JWKS_URL: 'https://sso.test/keys' };
  const inputs = {
    api: { ...common, DJANGO_SECRET_KEY: 'private-marker', DJANGO_ALLOWED_HOSTS: 'portal.test',
      DJANGO_DB_NAME: 'portal', DJANGO_DB_USER: 'portal', DJANGO_DB_PASSWORD: 'private-marker',
      DJANGO_DB_HOST: 'db.test', DJANGO_DB_PORT: '5432', DJANGO_CORS_ALLOWED_ORIGINS: 'https://portal.test',
      DJANGO_CSRF_TRUSTED_ORIGINS: 'https://portal.test', PUBLIC_API_BASE_URL: 'https://portal.test',
      ALLOWED_REDIRECT_HOSTS: 'portal.test', MINIO_ENDPOINT: 'https://storage.test',
      MINIO_ACCESS_KEY: 'private-marker', MINIO_SECRET_KEY: 'private-marker' },
    web: { VITE_SITE_URL: 'https://portal.test', VITE_BACKEND_URL: 'https://portal.test',
      BACKEND_API_URL: 'http://api.test', VITE_MINIO_ENDPOINT: 'https://storage.test' },
    minio: { MINIO_ROOT_USER: 'private-marker', MINIO_ROOT_PASSWORD: 'private-marker',
      MINIO_ACCESS_KEY: 'private-marker', MINIO_SECRET_KEY: 'private-marker',
      MINIO_SERVER_URL: 'https://storage.test', MINIO_BROWSER_REDIRECT_URL: '' },
  };
  return Object.entries(inputs[component]).map(([key, value]) => `${key}=${value}\n`).join('');
}

function checkPortal(t, component, content) {
  const input = path.join(sandbox(t), 'input.env');
  fs.writeFileSync(input, content, { mode: 0o600 });
  const result = spawnSync('bash', ['deploy/shared/scripts/check-env.sh', 'portal', 'prod', component, input], { cwd: root, encoding: 'utf8' });
  assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
  return result;
}

test('운영 API는 선택 업무 연동 없이 DB·Keycloak·MinIO 입력으로 검사한다', t => {
  const fixture = portalFixture('api');
  assert.equal(checkPortal(t, 'api', fixture).status, 0);
  assert.notEqual(checkPortal(t, 'api', fixture.replace('OIDC_PROVIDER=keycloak', 'OIDC_PROVIDER=adfs')).status, 0);
  assert.notEqual(checkPortal(t, 'api', fixture.replace(/^MINIO_SECRET_KEY=.*\n/m, '')).status, 0);
});

test('운영 Web·MinIO 검사는 미입력 상태를 차단하고 완성된 입력을 허용한다', t => {
  for (const component of ['web', 'minio']) {
    const example = portalFixture(component).replace(/=.+/g, '=');
    assert.notEqual(checkPortal(t, component, example).status, 0);
    assert.equal(checkPortal(t, component, portalFixture(component)).status, 0);
  }
});

test('운영 client 검사는 Portal DB·업무 연동 없이 독립적으로 실행한다', t => {
  const fixture = portalFixture('api').replace(/^DJANGO_DB_.*\n/gm, '').replace(/^MINIO_.*\n/gm, '');
  assert.equal(checkPortal(t, 'client', fixture).status, 0);
});

test('Kubernetes 입력 경로는 prod로 통일하고 미지원 환경을 적용하지 않는다', () => {
  const resolved = spawnSync('bash', ['-c', 'source deploy/shared/scripts/env-lib.sh; resolve_env_file "$PWD" portal prod api'], { cwd: root, encoding: 'utf8' });
  assert.equal(resolved.status, 0);
  assert.equal(resolved.stdout, path.join(root, 'deploy/portal/env/prod/api.env'));
  for (const profile of ['internal', 'stage', 'oidc']) {
    const result = spawnSync('bash', ['deploy/shared/scripts/apply-env.sh', 'portal', profile, 'api'], { cwd: root, encoding: 'utf8', env: { ...process.env, KUBECTL_BIN: '/not-a-real-kubectl' } });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /local 또는 prod/);
  }
});

test('앱별 설정 경로와 외부 env 검사는 실행 디렉터리에 의존하지 않는다', t => {
  const dir = sandbox(t);
  const library = path.join(root, 'deploy/shared/scripts/env-lib.sh');
  for (const [app, component, relative, profile = 'prod'] of [
    ['keycloak', 'server', 'keycloak/env/prod.env'],
    ['airflow', 'server', 'airflow/env/k8s.env'],
    ['monitoring', 'server', 'monitoring/env/k8s.env'],
    ['portal', 'client', 'portal/env/prod/api.env'],
    ['portal', 'web', 'portal/env/prod/web.env'],
    ['portal', 'minio', 'portal/env/prod/minio.env'],
    ['portal', 'api', '../local/portal/env/api.env', 'local'],
  ]) {
    const result = spawnSync('bash', ['-c', 'source "$1"; resolve_env_file "$2" "$3" "$5" "$4"', 'bash', library, root, app, component, profile], { cwd: dir, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, path.join(root, 'deploy', relative));
  }
  const input = path.join(dir, 'input.env');
  fs.writeFileSync(input, fixtures.server, { mode: 0o600 });
  const result = spawnSync('bash', [path.join(root, 'deploy/shared/scripts/check-env.sh'), 'keycloak', 'prod', 'server', input], { cwd: dir, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
});


test('추적 중인 env로 저장소 profile 검사를 통과한다', t => {
  const dir = sandbox(t);
  fs.mkdirSync(path.join(dir, 'deploy/shared/scripts'), { recursive: true });
  fs.copyFileSync(path.join(root, 'deploy/shared/scripts/validate_env_profile_keys.sh'), path.join(dir, 'deploy/shared/scripts/validate_env_profile_keys.sh'));
  fs.copyFileSync(path.join(root, 'deploy/shared/scripts/env-lib.sh'), path.join(dir, 'deploy/shared/scripts/env-lib.sh'));
  for (const relative of ['local/portal/env', 'local/shared/env', 'deploy/portal/env/test', 'deploy/airflow/env', 'deploy/monitoring/env', 'deploy/headlamp/env']) {
    fs.cpSync(path.join(root, relative), path.join(dir, relative), {
      recursive: true,
    });
  }
  fs.mkdirSync(path.join(dir, 'deploy/portal/env/prod'));
  fs.mkdirSync(path.join(dir, 'deploy/keycloak/env'), { recursive: true });
  fs.copyFileSync(path.join(root, 'deploy/keycloak/env/prod.env'), path.join(dir, 'deploy/keycloak/env/prod.env'));
  for (const component of ['api', 'web', 'minio']) {
    fs.copyFileSync(path.join(root, 'deploy/portal/env/prod', `${component}.env`), path.join(dir, 'deploy/portal/env/prod', `${component}.env`));
  }
  const result = spawnSync('bash', ['deploy/shared/scripts/validate_env_profile_keys.sh'], { cwd: dir, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
});

test('로컬 Makefile 진입점은 env를 합성하고 공통 도구에 전달한 뒤 임시 파일을 삭제한다', t => {
  const dir = sandbox(t);
  for (const relative of ['Makefile', 'deploy/shared/scripts/env-lib.sh', 'deploy/shared/scripts/apply-env.sh',
    'local/portal/scripts/build-local-api-env.sh', 'local/portal/scripts/apply-env.sh']) {
    const destination = path.join(dir, relative);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.copyFileSync(path.join(root, relative), destination);
  }
  const envDir = path.join(dir, 'local/portal/env');
  fs.mkdirSync(envDir);
  fs.writeFileSync(path.join(envDir, 'api.env'), portalFixture('api') + '\nLOCAL_BASE_MARKER=base\n');
  fs.writeFileSync(path.join(envDir, 'api-k8s.env'), 'LOCAL_BASE_MARKER=overlay\n');
  fs.writeFileSync(path.join(envDir, 'minio.env'), 'MINIO_ACCESS_KEY=client\nMINIO_SECRET_KEY=private-marker\nMINIO_ROOT_PASSWORD=excluded\n');
  const capture = path.join(dir, 'capture.json');
  const kubectl = path.join(dir, 'kubectl.cjs');
  fs.writeFileSync(kubectl, `#!/usr/bin/env node
const fs=require('node:fs');const args=process.argv.slice(2);
if(args[0]==='create'){
 const file=args.find(a=>a.startsWith('--from-env-file=')).slice('--from-env-file='.length);
 fs.writeFileSync(process.env.MOCK_CAPTURE,JSON.stringify({args,file,content:fs.readFileSync(file,'utf8')}));
 console.log('apiVersion: v1');
}else if(args[0]==='apply'){fs.readFileSync(0,'utf8');}else process.exit(1);
`, { mode: 0o700 });
  const result = spawnSync('make', ['k8s-env', 'APP=portal', 'PROFILE=local'], {
    cwd: dir, encoding: 'utf8', env: { ...process.env, KUBECTL_BIN: kubectl, MOCK_CAPTURE: capture },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
  const captured = JSON.parse(fs.readFileSync(capture, 'utf8'));
  assert.equal(captured.args[captured.args.indexOf('-n') + 1], 'tailwind-local');
  assert.match(captured.content, /^LOCAL_BASE_MARKER=overlay$/m);
  assert.match(captured.content, /^MINIO_ACCESS_KEY=client$/m);
  assert.ok(!captured.content.includes('MINIO_ROOT_PASSWORD'));
  assert.equal(fs.existsSync(captured.file), false);
  const prepared = result.stdout.match(/설정 입력: (.+) \/ 앱:/)[1];
  assert.equal(fs.existsSync(prepared), false);
});

test('공통 도구는 합성 파일 없는 로컬 API 입력을 kubectl 호출 전에 차단한다', () => {
  const result = spawnSync('bash', ['deploy/shared/scripts/apply-env.sh', 'portal', 'local', 'api'], {
    cwd: root, encoding: 'utf8', env: { ...process.env, KUBECTL_BIN: '/not-a-real-kubectl' },
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /합성된 env 파일/);
  assert.ok(!result.stderr.includes('/not-a-real-kubectl'));
});

test('prod API Secret은 준비된 API 입력만 기존 Namespace에 적용한다', t => {
  const dir = sandbox(t), input = path.join(dir, 'input.env'), capture = path.join(dir, 'capture.json');
  fs.writeFileSync(input, portalFixture('api'), { mode: 0o600 });
  const kubectl = path.join(dir, 'kubectl.cjs');
  fs.writeFileSync(kubectl, `#!/usr/bin/env node
const fs=require('node:fs');const args=process.argv.slice(2);
if(args[0]==='create'){
 const file=args.find(a=>a.startsWith('--from-env-file=')).split('=').slice(1).join('=');
 const keys=fs.readFileSync(file,'utf8').trim().split('\\n').map(l=>l.split('=')[0]);
 fs.writeFileSync(process.env.MOCK_CAPTURE,JSON.stringify({args,keys}));
 console.log('apiVersion: v1\\nkind: Secret');
}else if(args[0]==='apply'){fs.readFileSync(0,'utf8');console.log('applied');}else process.exit(1);
`, { mode: 0o700 });
  const result = spawnSync('bash', ['deploy/shared/scripts/apply-env.sh', 'portal', 'prod', 'api', input], { cwd: root, encoding: 'utf8', env: { ...process.env, KUBECTL_BIN: kubectl, MOCK_CAPTURE: capture } });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
  const captured = JSON.parse(fs.readFileSync(capture, 'utf8'));
  assert.equal(captured.args[captured.args.indexOf('-n') + 1], 'tailwind-internal');
  assert.ok(captured.keys.includes('MINIO_SECRET_KEY'));
  assert.ok(!captured.keys.includes('MINIO_ROOT_PASSWORD'));
});

function sandbox(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-env-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function check(dir, content, component = 'server') {
  const file = path.join(dir, 'input.env');
  fs.writeFileSync(file, content, { mode: 0o600 });
  const result = spawnSync('bash', ['deploy/shared/scripts/check-env.sh', 'keycloak', 'prod', component, file], { cwd: root, encoding: 'utf8' });
  assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
  return result;
}

test('서버 기동은 Portal·사내 OIDC 입력 없이 검사에 통과한다', t => {
  assert.equal(check(sandbox(t), fixtures.server).status, 0);
});

test('누락·중복·placeholder를 차단하며 값은 노출하지 않는다', t => {
  const dir = sandbox(t);
  for (const content of [fixtures.server.replace('postgres-password=db-test\n', ''), fixtures.server + 'postgres-password=private-marker\n', fixtures.server.replace('db-test', '<입력 필요>')]) {
    assert.notEqual(check(dir, content).status, 0);
  }
});

test('env 안의 shell 표현식을 실행하지 않는다', t => {
  const dir = sandbox(t);
  const marker = path.join(dir, 'executed');
  const result = check(dir, fixtures.server.replace('db-test', '$(touch ' + marker + ')'));
  assert.equal(result.status, 0);
  assert.equal(fs.existsSync(marker), false);
});

test('사내 OIDC 검증은 명시적 인증 방식과 서명 검증 입력을 확인한다', t => {
  const dir = sandbox(t);
  assert.equal(check(dir, fixtures.oidc, 'oidc').status, 0);
  assert.notEqual(check(dir, fixtures.oidc.replace('CORP_OIDC_JWKS_URL=https://idp.test/keys\n', ''), 'oidc').status, 0);
  assert.notEqual(check(dir, fixtures.oidc.replace('client_secret_post', 'unknown'), 'oidc').status, 0);
  assert.equal(check(dir, fixtures.oidc.replace('SIGNATURE=true', 'SIGNATURE=false').replace('CORP_OIDC_JWKS_URL=https://idp.test/keys\n', ''), 'oidc').status, 0);
});

function mockAdmin(t, { existing = true, fail = '' } = {}) {
  const dir = sandbox(t);
  const log = path.join(dir, 'calls.jsonl');
  const state = path.join(dir, 'client');
  if (existing) fs.writeFileSync(state, 'exists');
  const mock = path.join(dir, 'kcadm.cjs');
  // 생성·갱신 분기와 오류 시 추가 변경 중단을 실제 Bash 스크립트로 검증합니다.
  fs.writeFileSync(mock, `#!/usr/bin/env node
const fs = require('node:fs');
const a = process.argv.slice(2);
fs.appendFileSync(process.env.MOCK_LOG, JSON.stringify(a)+'\\n');
if(a[0]!=='config' && a.includes('--realm')) process.exit(2);
if(process.env.MOCK_FAIL && a[0]==='get' && a[1].includes(process.env.MOCK_FAIL)) { console.error('private-marker'); process.exit(1); }
if(a[0]==='get') {
 if(a[1]==='identity-provider/instances') console.log(process.env.MOCK_EXISTING==='true'?'oidc':'');
 else if(a[1]==='realms') console.log(process.env.MOCK_EXISTING==='true'?'master,unused'.replace(',', '\\n')+'\\netch':'master');
 else if(a[1]==='realms/etch') console.log(process.env.MOCK_EMAIL_AS_USERNAME || 'false');
 else if(a[1]==='clients') console.log(fs.existsSync(process.env.MOCK_STATE)?'client-uuid':'');
 else if(a[1].endsWith('/mappers')||a[1].endsWith('/models')) console.log(process.env.MOCK_RETIRED==='1'?'old-grade,grdName\\nold-origin,origincomp\\nold-first,first_name\\nold-last,last_name\\nold-userid,userid':process.env.MOCK_EPID_EXISTING==='1'?'existing-epid,epid-username\\nexisting-sabun,sabun':'existing-sabun,sabun');
 else console.log('{}');
}
if(a[0]==='create'&&a[1]==='clients')fs.writeFileSync(process.env.MOCK_STATE,'exists');
`, { mode: 0o700 });
  // 컨테이너에서는 역할별 원본이 같은 ConfigMap 디렉터리에 마운트됩니다.
  const configDirectory = path.join(dir, 'config-files');
  fs.mkdirSync(configDirectory);
  for (const relative of ['oidc/admin-common.sh', 'oidc/setup-oidc.sh', 'claims/sync-oidc-claim-mappers.sh', 'claims/account-user-profile.json']) {
    fs.copyFileSync(path.join(root, 'deploy/keycloak/k8s', relative), path.join(configDirectory, path.basename(relative)));
  }
  const env = { ...process.env, KCADM_BIN: mock, MOCK_LOG: log, MOCK_STATE: state, MOCK_EXISTING: String(existing), MOCK_FAIL: fail,
    KEYCLOAK_ADMIN_USERNAME: 'admin', KEYCLOAK_ADMIN_PASSWORD: 'private-marker', KCADM_CONFIG: path.join(dir, 'config'),
    KEYCLOAK_CONFIG_DIR: configDirectory, KEYCLOAK_TARGET_REALM: 'etch', KEYCLOAK_IDP_ALIAS: 'oidc',
    KEYCLOAK_PUBLIC_URL: 'https://sso.test', OIDC_PROVIDER: 'keycloak', OIDC_CLIENT_ID: 'portal', OIDC_CLIENT_SECRET: 'private-marker',
    OIDC_ISSUER: 'https://sso.test/realms/etch', OIDC_REDIRECT_URI: 'https://portal.test/auth/keycloak/callback/', FRONTEND_BASE_URL: 'https://portal.test' };
  for (const line of fixtures.oidc.trim().split('\n')) { const index = line.indexOf('='); env[line.slice(0, index)] = line.slice(index + 1); }
  return {
    env,
    run(script, extra = {}) {
      const result = spawnSync('bash', [script], { cwd: root, encoding: 'utf8', env: { ...env, ...extra } });
      assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
      return result;
    },
    calls() { return fs.readFileSync(log, 'utf8').trim().split('\n').map(JSON.parse); },
  };
}

for (const existing of [false, true]) {
  test(`사내 IdP ${existing ? '갱신' : '생성'}은 realm과 client를 변경하지 않는다`, t => {
    const mock = mockAdmin(t, { existing });
    assert.equal(mock.run('deploy/keycloak/k8s/oidc/setup-oidc.sh').status, 0);
    const writes = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]));
    assert.equal(writes.length, 1);
    assert.equal(writes[0][0], existing ? 'update' : 'create');
    assert.equal(writes[0][1], existing ? 'identity-provider/instances/oidc' : 'identity-provider/instances');
    assert.ok(writes[0].includes('config.clientAuthMethod="client_secret_post"'));
  });

  test(`Portal ${existing ? '갱신' : '생성'}과 token mapper는 사내 IdP를 변경하지 않는다`, t => {
    const mock = mockAdmin(t, { existing });
    const result = mock.run('deploy/portal/k8s/jobs/keycloak-client/setup-client.sh');
    assert.equal(result.status, 0, result.stderr);
    const writes = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]));
    assert.equal(writes.length, 19);
    assert.equal(writes[0][0], existing ? 'update' : 'create');
    assert.ok(writes.every(a => a[1].startsWith('clients')));
    assert.equal(writes.filter(a => a[1].includes('/protocol-mappers/')).length, 18);
  });
}

test('IdP mapper는 Portal client 없이 15개 속성과 EPID username을 설정한다', t => {
  const mock = mockAdmin(t, { existing: false });
  const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: 'idp' });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(mock.calls().every(a => !a[1].startsWith('clients')));
  const writes = mock.calls().filter(a => ['create', 'update'].includes(a[0]) && a.includes('identityProviderMapper=oidc-user-attribute-idp-mapper'));
  assert.equal(writes.length, 15);
  const profileWrites = mock.calls().filter(a => a[0] === 'update' && a[1] === 'users/profile');
  assert.equal(profileWrites.length, 1);
  assert.ok(profileWrites[0].includes('-n'));
  assert.ok(profileWrites[0].includes(path.join(mock.env.KEYCLOAK_CONFIG_DIR, 'account-user-profile.json')));
  assert.ok(writes.every(a => a.includes('identityProviderMapper=oidc-user-attribute-idp-mapper')));
  assert.ok(writes.every(a => JSON.parse(a.find(v => v.startsWith('config=')).slice(7)).syncMode === 'FORCE'));
});

test('claim Job은 기존 읽기 전용 스크립트의 realm 옵션을 사본에서 교정한다', t => {
  const dir = sandbox(t);
  const source = path.join(dir, 'source.sh');
  const target = path.join(dir, 'run.sh');
  const script = 'printf "%s\\n" --realm "$KEYCLOAK_TARGET_REALM"\n';
  fs.writeFileSync(source, script, { mode: 0o400 });
  for (const relative of ['deploy/keycloak/k8s/claims/claim-mappers-job.yaml', 'deploy/keycloak/rendered/internal-keycloak-claim-mappers.yaml']) {
    const job = require('js-yaml').loadAll(fs.readFileSync(path.join(root, relative), 'utf8')).find(r => r.kind === 'Job');
    const command = job.spec.template.spec.containers[0].command;
    const body = command[2].replaceAll('/opt/keycloak-config/sync-oidc-claim-mappers.sh', source)
      .replaceAll('/tmp/sync-oidc-claim-mappers.sh', target);
    const result = spawnSync(command[0], [command[1], body], { encoding: 'utf8', env: { ...process.env, KEYCLOAK_TARGET_REALM: 'etch' } });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, '-r\netch\n');
    assert.equal(fs.readFileSync(source, 'utf8'), script);
    assert.equal(fs.readFileSync(target + '.before-realm-fix', 'utf8'), script);
  }
});

test('IdP 조회 실패는 새 IdP 생성으로 처리하지 않는다', t => {
  const mock = mockAdmin(t, { fail: 'identity-provider/instances' });
  assert.notEqual(mock.run('deploy/keycloak/k8s/oidc/setup-oidc.sh').status, 0);
  assert.equal(mock.calls().some(a => ['create', 'update'].includes(a[0])), false);
});

test('mapper 조회 실패는 중복 생성으로 처리하지 않는다', t => {
  const mock = mockAdmin(t, { fail: '/mappers' });
  assert.notEqual(mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: 'idp' }).status, 0);
  assert.equal(mock.calls().some(a => a[0] === 'create'), false);
});

test('대상 Keycloak과 다른 issuer로 client를 등록하지 않는다', t => {
  const mock = mockAdmin(t);
  assert.notEqual(mock.run('deploy/portal/k8s/jobs/keycloak-client/setup-client.sh', { OIDC_ISSUER: 'https://another.test/realms/etch' }).status, 0);
});

test('JSON 특수문자가 있는 client secret을 변형하지 않는다', t => {
  const mock = mockAdmin(t);
  const secret = 'quote" slash\\ dollar$';
  const result = mock.run('deploy/portal/k8s/jobs/keycloak-client/setup-client.sh', { OIDC_CLIENT_SECRET: secret });
  assert.equal(result.status, 0, result.stderr);
  const call = mock.calls().find(a => a[0] === 'update' && a[1] === 'clients/client-uuid');
  assert.equal(JSON.parse(call.find(a => a.startsWith('secret=')).slice(7)), secret);
});

for (const component of ['server', 'oidc']) {
  test(`${component} Secret에는 해당 작업의 입력만 전달한다`, t => {
    const dir = sandbox(t), input = path.join(dir, 'input.env'), captured = path.join(dir, 'selected.env');
    fs.writeFileSync(input, fixtures.server + fixtures.oidc);
    const kubectl = path.join(dir, 'kubectl.cjs');
    fs.writeFileSync(kubectl, `#!/usr/bin/env node
const fs=require('node:fs');const args=process.argv.slice(2);
if(args[0]==='create'){
 const flag=args.find(a=>a.startsWith('--from-env-file='));
 fs.copyFileSync(flag.slice('--from-env-file='.length),process.env.MOCK_CAPTURE);
 console.log('apiVersion: v1\\nkind: Secret\\nmetadata:\\n  name: test');
}else if(args[0]==='apply'){fs.readFileSync(0,'utf8');console.log('secret configured');}
else process.exit(1);
`, { mode: 0o700 });
    const result = spawnSync('bash', ['deploy/shared/scripts/apply-env.sh', 'keycloak', 'prod', component, input], { cwd: root, encoding: 'utf8', env: { ...process.env, KUBECTL_BIN: kubectl, MOCK_CAPTURE: captured } });
    assert.equal(result.status, 0, result.stderr);
    assert.ok(!(result.stdout + result.stderr).includes('private-marker'));
    const keys = fs.readFileSync(captured, 'utf8').trim().split('\n').map(l => l.split('=')[0]);
    if (component === 'server') assert.deepEqual(keys.sort(), ['postgres-password', 'bootstrap-admin-username', 'bootstrap-admin-password', 'keycloak-public-url'].sort());
    else assert.ok(keys.every(k => k.startsWith('CORP_OIDC_')));
  });
}

test('account_user 프로필과 양방향 mapper는 로그인 ID와 사람 이름을 분리한다', t => {
  const profile = JSON.parse(fs.readFileSync(path.join(root, 'deploy/keycloak/k8s/claims/account-user-profile.json'), 'utf8'));
  const byName = Object.fromEntries(profile.attributes.map(a => [a.name, a]));
  const mapping = { loginid: 'loginid', userid: 'username', sabun: 'sabun', username: 'display_name', username_en: 'username_en', givenname: 'firstName', surname: 'lastName', deptname: 'deptname', deptid: 'deptid', mail: 'email', grdName: 'grdName', grdname_en: 'grdname_en', busname: 'busname', intcode: 'intcode', intname: 'intname', employeetype: 'employeetype', user_sdwt_prod: 'user_sdwt_prod', line_id: 'line_id' };
  assert.deepEqual(new Set(Object.keys(byName)), new Set(['username', 'firstName', 'lastName', ...Object.values(mapping)]));
  assert.ok(!byName.career_level);
  // 활성 필드는 본인 조회만 허용하고 신원 정보 수정은 관리자에게 제한합니다.
  for (const attribute of profile.attributes) {
    assert.deepEqual(attribute.permissions, { view: ['admin', 'user'], edit: ['admin'] });
  }
  assert.equal(profile.unmanagedAttributePolicy, 'ADMIN_EDIT');
  for (const name of ['firstName', 'lastName']) {
    assert.ok(!byName[name].required);
  }
  assert.equal(byName.deptname.validations.length.max, 128);
  assert.equal(byName.sabun.validations.length.max, 50);
  assert.ok(!byName.password && !byName.is_superuser);
  assert.ok(!byName.first_name && !byName.last_name && !byName.avatarid);
  assert.ok(!byName.givenname && !byName.surname);
  const mock = mockAdmin(t);
  assert.equal(mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh').status, 0);
  const writes = mock.calls().filter(a => ['create', 'update'].includes(a[0]) && !a.includes('identityProviderMapper=oidc-username-idp-mapper') && (a[1].includes('/mappers') || a[1].includes('/protocol-mappers/')));
  assert.equal(writes.length, 33);
  for (const args of writes) {
    const claim = args.find(a => a.startsWith('name=')).slice(5);
    const config = JSON.parse(args.find(a => a.startsWith('config=')).slice(7));
    assert.equal(config['user.attribute'], mapping[claim]);
    if (claim === 'userid') assert.ok(args[1].startsWith('clients/'));
    else assert.notEqual(config['user.attribute'], 'username');
    if (args[1].startsWith('clients/')) {
      assert.equal(config['claim.name'], claim);
      assert.ok(args.includes(`protocolMapper=${['userid', 'mail', 'givenname', 'surname'].includes(claim) ? 'oidc-usermodel-property-mapper' : 'oidc-usermodel-attribute-mapper'}`));
    } else {
      assert.equal(config.claim, claim);
      assert.equal(config.syncMode, 'FORCE');
    }
  }
});

test('소속 속성은 본인 수정과 사내 IdP 갱신을 막고 앱에만 전달한다', t => {
  const names = ['user_sdwt_prod', 'line_id'];
  const profile = JSON.parse(fs.readFileSync(path.join(root, 'deploy/keycloak/k8s/claims/account-user-profile.json'), 'utf8'));
  for (const name of names) {
    const attribute = profile.attributes.find(item => item.name === name);
    assert.deepEqual(attribute.permissions, { view: ['admin', 'user'], edit: ['admin'] });
    assert.equal(attribute.multivalued, false);
    assert.equal(attribute.required, undefined);
  }
  const mock = mockAdmin(t);
  const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh');
  assert.equal(result.status, 0, result.stderr);
  const writes = mock.calls().filter(a => ['create', 'update'].includes(a[0]));
  const local = JSON.parse(fs.readFileSync(path.join(root, 'local/keycloak/k8s/realm-portal.json'), 'utf8'));
  for (const name of names) {
    const mappings = writes.filter(a => a.includes(`name=${name}`));
    assert.equal(mappings.length, 1);
    assert.ok(mappings[0][1].startsWith('clients/'));
    assert.ok(mappings[0].includes('protocolMapper=oidc-usermodel-attribute-mapper'));
    const config = JSON.parse(mappings[0].find(a => a.startsWith('config=')).slice(7));
    assert.equal(config['user.attribute'], name);
    assert.equal(config['claim.name'], name);
    assert.equal(config['jsonType.label'], 'String');
    assert.equal(config.multivalued, 'false');
    for (const flag of ['id.token.claim', 'access.token.claim', 'userinfo.token.claim']) {
      assert.equal(config[flag], 'true');
    }
    assert.deepEqual(local.clients[0].protocolMappers.find(m => m.name === name).config, config);
  }
});

test('mapper 전달 YAML은 서버 변경 없이 프로필·스크립트와 실패 로그 보존 Job을 적용한다', () => {
  const yaml = require('js-yaml');
  const resources = yaml.loadAll(fs.readFileSync(path.join(root, 'deploy/keycloak/rendered/internal-keycloak-claim-mappers.yaml'), 'utf8'));
  assert.deepEqual(resources.map(r => r.kind), ['ConfigMap', 'Job']);
  const [config, job] = resources;
  assert.equal(config.metadata.name, job.spec.template.spec.volumes.find(v => v.name === 'config').configMap.name);
  const sources = {
    'account-user-profile.json': 'claims/account-user-profile.json',
    'sync-oidc-claim-mappers.sh': 'claims/sync-oidc-claim-mappers.sh',
    'admin-common.sh': 'oidc/admin-common.sh',
    'setup-oidc.sh': 'oidc/setup-oidc.sh',
    'setup-realm.sh': 'oidc/setup-realm.sh',
    'etch-realm.json': 'server/etch-realm.json',
  };
  for (const [file, value] of Object.entries(config.data)) {
    assert.equal(value, fs.readFileSync(path.join(root, 'deploy/keycloak/k8s', sources[file]), 'utf8'));
  }
  assert.ok(config.data['account-user-profile.json']);
  assert.equal(job.spec.backoffLimit, 0);
  assert.equal(job.spec.template.spec.restartPolicy, 'Never');
});

test('폐기한 mapper를 삭제하되 Portal userid 출력은 보존한다', t => {
  for (const target of ['idp', 'client']) {
    const mock = mockAdmin(t);
    const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: target, MOCK_RETIRED: '1' });
    assert.equal(result.status, 0, result.stderr);
    const gradeUpdate = mock.calls().find(a => a[0] === 'update' && a[1].endsWith('/old-grade'));
    assert.ok(gradeUpdate);
    assert.ok(gradeUpdate.includes('name=grdName'));
    assert.equal(JSON.parse(gradeUpdate.find(a => a.startsWith('config=')).slice(7))['user.attribute'], 'grdName');
    const deleted = mock.calls().filter(a => a[0] === 'delete');
    assert.equal(deleted.length, target === 'idp' ? 4 : 3);
    assert.ok(deleted.every(a => a[1].startsWith(target === 'idp' ? 'identity-provider/' : 'clients/')));
    assert.deepEqual(deleted.map(a => a[1].split('/').at(-1)).sort(), target === 'idp' ? ['old-first', 'old-last', 'old-origin', 'old-userid'] : ['old-first', 'old-last', 'old-origin']);
  }
  const profile = JSON.parse(fs.readFileSync(path.join(root, 'deploy/keycloak/k8s/claims/account-user-profile.json'), 'utf8'));
  assert.ok(!profile.attributes.some(a => a.name === 'origincomp'));
  assert.ok(profile.attributes.some(a => a.name === 'grdName'));
  assert.ok(profile.attributes.some(a => a.name === 'grdname_en'));
});

for (const existing of [false, true]) {
  test(`EPID username mapper ${existing ? '갱신' : '생성'}은 LOCAL/FORCE와 userid를 사용한다`, t => {
    const mock = mockAdmin(t);
    const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: 'idp', MOCK_EPID_EXISTING: existing ? '1' : '0' });
    assert.equal(result.status, 0, result.stderr);
    const writes = mock.calls().filter(a => ['create', 'update'].includes(a[0]) && a.includes('identityProviderMapper=oidc-username-idp-mapper'));
    assert.equal(writes.length, 1);
    assert.equal(writes[0][0], existing ? 'update' : 'create');
    assert.equal(writes[0][1], `identity-provider/instances/oidc/mappers${existing ? '/existing-epid' : ''}`);
    assert.ok(writes[0].includes('name=epid-username'));
    assert.deepEqual(JSON.parse(writes[0].find(a => a.startsWith('config=')).slice(7)), { syncMode: 'FORCE', template: '${CLAIM.userid}', target: 'LOCAL' });
    const userWrites = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]) && a[1].startsWith('users/'));
    assert.ok(userWrites.every(a => a[1] === 'users/profile'));
  });
}

test('Email as username 또는 realm 조회 실패는 설정 변경 전에 중단한다', t => {
  for (const scenario of ['true', 'invalid', 'read-failed']) {
    const mock = mockAdmin(t, { fail: scenario === 'read-failed' ? 'realms/etch' : '' });
    const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: 'idp', MOCK_EMAIL_AS_USERNAME: scenario });
    assert.notEqual(result.status, 0);
    assert.ok(!mock.calls().some(a => ['create', 'update', 'delete'].includes(a[0])));
  }
});

test('Portal client 전용 실행은 realm username 정책과 EPID mapper를 변경하지 않는다', t => {
  const mock = mockAdmin(t);
  const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_MAPPING_TARGET: 'client', MOCK_EMAIL_AS_USERNAME: 'true' });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!mock.calls().some(a => a[1] === 'realms/etch' || a.includes('identityProviderMapper=oidc-username-idp-mapper')));
});




test('기본 개발·종료는 Kubernetes를 사용하며 검사는 실제 클러스터를 변경하지 않는다', () => {
  for (const [target, command] of [['dev', 'up'], ['down', 'down']]) {
    const result = spawnSync('make', ['-n', target], { cwd: root, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, new RegExp(`local/shared/scripts/k8s.py ${command}`));
  }
});

test('폐기된 oidc profile 검사는 실제 파일을 읽기 전에 실패한다', () => {
  for (const args of [
    ['deploy/shared/scripts/validate_env_profile_keys.sh', 'all', 'oidc'],
    ['deploy/shared/scripts/check-env.sh', 'portal', 'oidc', 'api', '/not-a-real-input'],
  ]) {
    const result = spawnSync('bash', args, { cwd: root, encoding: 'utf8' });
    assert.notEqual(result.status, 0);
    assert.doesNotMatch(result.stderr, /설정 파일이 없습니다/);
  }
});

test('Helm 앱 env 검사는 전용 Kubernetes 검사에 외부 입력을 그대로 전달한다', t => {
  const dir = sandbox(t);
  const capture = path.join(dir, 'args.json');
  fs.writeFileSync(path.join(dir, 'python3'), `#!/usr/bin/env node
require('node:fs').writeFileSync(process.env.MOCK_CAPTURE, JSON.stringify(process.argv.slice(2)));
`, { mode: 0o700 });
  for (const app of ['airflow', 'monitoring', 'headlamp']) {
    const input = path.join(dir, 'external.env');
    const result = spawnSync('bash', ['deploy/shared/scripts/check-env.sh', app, 'prod', 'server', input], {
      cwd: root, encoding: 'utf8', env: { ...process.env, PATH: `${dir}:${process.env.PATH}`, MOCK_CAPTURE: capture },
    });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(fs.readFileSync(capture)), [path.join(root, `deploy/${app}/scripts/manage.py`), 'check', '--env', input]);
  }
});

for (const existing of [false, true]) {
  test(`realm 단계는 ${existing ? '기존 realm을 보존' : '없는 realm만 생성'}한다`, t => {
    const mock = mockAdmin(t, { existing });
    const result = mock.run('deploy/keycloak/k8s/oidc/setup-realm.sh');
    assert.equal(result.status, 0, result.stderr);
    const writes = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]));
    assert.equal(writes.length, existing ? 0 : 1);
    if (!existing) assert.equal(writes[0][1], 'realms');
  });
}
test('realm 조회 실패는 새 realm 생성으로 이어지지 않는다', t => {
  const mock = mockAdmin(t, { fail: 'realms' });
  assert.notEqual(mock.run('deploy/keycloak/k8s/oidc/setup-realm.sh').status, 0);
  assert.ok(!mock.calls().some(a => ['create', 'update', 'delete'].includes(a[0])));
});
test('프로필 전용 단계는 IdP·client·mapper를 변경하지 않는다', t => {
  const mock = mockAdmin(t, { fail: 'identity-provider' });
  const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', { KEYCLOAK_PROFILE_ONLY: 'true' });
  assert.equal(result.status, 0, result.stderr);
  const writes = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]));
  assert.equal(writes.length, 1);
  assert.equal(writes[0][1], 'users/profile');
});
test('IdP mapper 전용 단계는 User Profile과 client를 변경하지 않는다', t => {
  const mock = mockAdmin(t);
  const result = mock.run('deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh', {
    KEYCLOAK_MAPPING_TARGET: 'idp', KEYCLOAK_SKIP_PROFILE: 'true',
  });
  assert.equal(result.status, 0, result.stderr);
  const writes = mock.calls().filter(a => ['create', 'update', 'delete'].includes(a[0]));
  assert.equal(writes.length, 16);
  assert.ok(writes.every(a => a[1].startsWith('identity-provider/instances/oidc/mappers')));
});
