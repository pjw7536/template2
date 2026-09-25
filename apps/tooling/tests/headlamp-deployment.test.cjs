const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const yaml = require('js-yaml');
const root = path.resolve(__dirname, '../../..');

function run(args, cwd = root) {
  const result = spawnSync('python3', args, { cwd, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

test('Headlamp 입력 오류와 context 누락은 클러스터 변경 전에 차단한다', () => {
  run(['-m', 'unittest', 'discover', '-s', 'deploy/headlamp/tests', '-v']);
});

test('Headlamp 서버 단독 구성은 Keycloak 관리자 그룹에만 전체 관리 권한을 연결한다', t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'headlamp-server-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  fs.cpSync(path.join(root, 'deploy/headlamp'), path.join(directory, 'deploy/headlamp'), {
    recursive: true, filter: file => !file.endsWith('.env') && !file.endsWith('.bak'),
  });
  // 서버 단독 checkout에서도 OIDC Secret을 참조하고 비밀값을 렌더하지 않습니다.
  const env = path.join(directory, 'headlamp.env');
  fs.writeFileSync(env, [
    'HEADLAMP_REGISTRY=mirror.example.test/ghcr',
    'HEADLAMP_HOST=ui.example.test', 'HEADLAMP_TLS_SECRET=headlamp-tls',
    'HEADLAMP_OIDC_ISSUER_URL=https://sso.example.test/realms/etch',
    'HEADLAMP_OIDC_CLIENT_ID=headlamp', 'HEADLAMP_OIDC_SECRET=headlamp-oidc',
    'HEADLAMP_OIDC_CA_CONFIGMAP=headlamp-ca', '',
  ].join('\n'));
  const rendered = run(['deploy/headlamp/scripts/manage.py', 'render', '--env', env], directory);
  const docs = yaml.loadAll(rendered).filter(Boolean);
  assert.equal(docs.some(doc => ['Secret', 'PersistentVolumeClaim'].includes(doc.kind)), false);
  const deployment = docs.find(doc => doc.kind === 'Deployment');
  const pod = deployment.spec.template.spec;
  assert.equal(pod.serviceAccountName, 'headlamp');
  assert.equal(pod.containers.length, 1);
  assert.equal(pod.containers[0].image, 'mirror.example.test/ghcr/headlamp-k8s/headlamp:v0.45.0');
  assert.doesNotMatch(JSON.stringify(pod), /unsafe-use-service-account-token/);
  assert.deepEqual(pod.containers[0].envFrom, [{ secretRef: { name: 'headlamp-oidc' } }]);
  const envMap = Object.fromEntries(pod.containers[0].env.map(item => [item.name, item.value]));
  assert.equal(envMap.OIDC_CALLBACK_URL, 'https://ui.example.test/headlamp/oidc-callback');
  assert.equal(envMap.OIDC_ISSUER_URL, 'https://sso.example.test/realms/etch');
  assert.equal(envMap.OIDC_CLIENT_SECRET, undefined);
  assert.equal(envMap.OIDC_USE_PKCE, 'true');
  assert.ok(pod.containers[0].args.includes('-oidc-client-secret=$(OIDC_CLIENT_SECRET)'));
  assert.ok(pod.containers[0].args.includes('-oidc-callback-url=$(OIDC_CALLBACK_URL)'));
  assert.ok(pod.containers[0].args.includes('-oidc-use-pkce=$(OIDC_USE_PKCE)'));
  assert.equal(envMap.SSL_CERT_FILE, '/etc/headlamp-ca/ca.crt');
  assert.ok(pod.volumes.some(volume => volume.configMap?.name === 'headlamp-ca'));
  assert.equal(docs.some(doc => doc.kind === 'ServiceAccount' && doc.metadata.name === 'headlamp-viewer'), false);
  assert.equal(docs.find(doc => doc.kind === 'Service').spec.type, 'ClusterIP');
  const bindings = docs.filter(doc => doc.kind === 'ClusterRoleBinding');
  assert.deepEqual(bindings.map(doc => doc.roleRef.name).sort(), ['cluster-admin']);
  for (const binding of bindings) {
    assert.deepEqual(binding.subjects, [{ kind: 'Group', name: 'headlamp:/headlamp-admins', apiGroup: 'rbac.authorization.k8s.io' }]);
  }
  assert.equal(bindings[0].metadata.name, 'server-headlamp-admin');
  assert.equal(docs.some(doc => doc.kind === 'ClusterRole'), false);
  assert.doesNotMatch(rendered, /server-headlamp-viewer|server-headlamp-discovery|headlamp-viewers/);
  const paths = run(['deploy/shared/scripts/app-paths.py', 'headlamp']).trim().split('\n');
  assert.deepEqual(paths, ['deploy/shared', 'docs', 'deploy/headlamp']);

  const ingress = docs.find(doc => doc.kind === 'Ingress');
  assert.equal(ingress.spec.ingressClassName, 'traefik');
  assert.deepEqual(ingress.spec.tls, [{ hosts: ['ui.example.test'], secretName: 'headlamp-tls' }]);
  assert.equal(ingress.spec.rules[0].http.paths[0].path, '/headlamp');
});
