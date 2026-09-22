const assert = require('node:assert/strict');
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

function identity(item) {
  return [item.apiVersion, item.kind, item.metadata.namespace || '', item.metadata.name].join('/');
}

test('로컬 집계는 앱별 리소스와 namespace·권한·ConfigMap 참조를 그대로 유지한다', () => {
  const all = render('local/shared/k8s');
  const byId = new Map(all.map(item => [identity(item), item]));
  assert.equal(byId.size, all.length, '집계에 중복 리소스가 없어야 합니다.');
  for (const app of ['portal', 'keycloak', 'headlamp', 'adfs_dummy']) {
    for (const item of render(`local/${app}/k8s`)) {
      assert.deepEqual(byId.get(identity(item)), item, identity(item));
    }
  }
  const deployments = all.filter(item => item.kind === 'Deployment');
  assert.deepEqual(deployments.map(item => item.metadata.name).sort(),
    ['adfs', 'api', 'edge-nginx', 'headlamp', 'keycloak', 'minio', 'traefik', 'web']);
  assert.ok(deployments.every(item => item.metadata.namespace === 'tailwind-local'));
  for (const binding of all.filter(item => ['RoleBinding', 'ClusterRoleBinding'].includes(item.kind))) {
    for (const subject of binding.subjects.filter(item => item.kind === 'ServiceAccount')) {
      assert.ok(all.some(item => item.kind === 'ServiceAccount' && item.metadata.name === subject.name
        && item.metadata.namespace === subject.namespace), identity(binding));
    }
  }
});

test('앱별 렌더는 다른 앱 Deployment를 포함하지 않고 Keycloak realm 참조가 해석된다', () => {
  const owners = { portal: ['api', 'edge-nginx', 'minio', 'web'], keycloak: ['keycloak'],
    headlamp: ['headlamp'], adfs_dummy: ['adfs'] };
  for (const [app, names] of Object.entries(owners)) {
    const items = render(`local/${app}/k8s`);
    assert.deepEqual(items.filter(item => item.kind === 'Deployment').map(item => item.metadata.name).sort(), names);
    if (app === 'keycloak') {
      const workload = items.find(item => item.kind === 'Deployment');
      const name = workload.spec.template.spec.volumes.find(item => item.name === 'realm').configMap.name;
      const realm = items.find(item => item.kind === 'ConfigMap' && item.metadata.name === name);
      assert.equal(JSON.parse(realm.data['realm-portal.json']).realm, 'portal');
      assert.ok(items.some(item => item.kind === 'Service' && item.metadata.name === 'keycloak'));
    }
  }
});
