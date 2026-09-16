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

test('Headlamp 서버 단독 구성은 토큰 조회 권한과 localhost용 Service만 생성한다', t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'headlamp-server-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  fs.cpSync(path.join(root, 'deploy/headlamp'), path.join(directory, 'deploy/headlamp'), { recursive: true });
  const rendered = run(['deploy/headlamp/scripts/manage.py', 'render'], directory);
  const docs = yaml.loadAll(rendered).filter(Boolean);
  assert.equal(docs.some(doc => ['Ingress', 'Secret', 'PersistentVolumeClaim'].includes(doc.kind)), false);
  const deployment = docs.find(doc => doc.kind === 'Deployment');
  const pod = deployment.spec.template.spec;
  assert.equal(pod.serviceAccountName, 'headlamp');
  assert.equal(pod.containers.length, 1);
  assert.equal(pod.containers[0].image, 'repository.samsungds.net/proxy-docker-ghcr.io/headlamp-k8s/headlamp:v0.45.0');
  assert.doesNotMatch(JSON.stringify(pod), /oidc|unsafe-use-service-account-token/);
  assert.equal(docs.find(doc => doc.kind === 'Service').spec.type, 'ClusterIP');
  const bindings = docs.filter(doc => doc.kind === 'ClusterRoleBinding');
  assert.deepEqual(bindings.map(doc => doc.roleRef.name).sort(), ['server-headlamp-discovery', 'view']);
  for (const binding of bindings) {
    assert.deepEqual(binding.subjects, [{ kind: 'ServiceAccount', name: 'headlamp-viewer', namespace: 'headlamp' }]);
  }
  const rules = docs.find(doc => doc.kind === 'ClusterRole').rules;
  assert.deepEqual(rules, [{ apiGroups: [''], resources: ['nodes', 'namespaces'], verbs: ['get', 'list', 'watch'] }]);
  const paths = run(['deploy/shared/scripts/app-paths.py', 'headlamp']).trim().split('\n');
  assert.deepEqual(paths, ['deploy/shared', 'docs', 'deploy/headlamp']);
});
