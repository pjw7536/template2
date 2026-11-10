const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');

test('로컬 Monitoring은 서버 env 계약을 만족하고 공개 Ingress를 생성하지 않는다', () => {
  const result = spawnSync('python3', ['-c', `
import json
import sys
sys.path.insert(0, 'local/shared/scripts')
from k8s_config import module, monitoring_settings
server = module('monitoring')
settings = monitoring_settings()
server.validate(settings)
print(json.dumps(server.values(settings)))
`], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const values = JSON.parse(result.stdout);
  for (const component of ['grafana', 'prometheus', 'alertmanager']) {
    assert.equal(values[component].ingress, undefined);
  }
});

test('로컬 Headlamp는 서버 chart를 재사용하며 접두사와 OIDC callback을 유지한다', () => {
  const result = spawnSync('python3', ['-c', `
import json
import sys
sys.path.insert(0, 'local/headlamp')
import local_oidc
print(json.dumps(local_oidc.render()))
`], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const resources = JSON.parse(result.stdout);
  const pod = resources.find(item => item.kind === 'Deployment').spec.template.spec;
  const container = pod.containers[0];
  const env = Object.fromEntries(container.env.map(item => [item.name, item.value]));
  assert.ok(container.args.includes('-base-url=/headlamp'));
  assert.equal(env.OIDC_CALLBACK_URL, 'https://localhost:8443/headlamp/oidc-callback');
  assert.equal(env.OIDC_ISSUER_URL, 'https://sso.localhost:8443/realms/local-platform');
  const ingress = resources.find(item => item.kind === 'Ingress');
  assert.equal(ingress.spec.rules[0].host, 'localhost');
  assert.deepEqual(ingress.spec.rules[0].http.paths.map(item => item.path), ['/headlamp']);
  assert.deepEqual(ingress.spec.tls, [{ secretName: 'headlamp-tls', hosts: ['localhost'] }]);
});

test('로컬 Airflow 메일은 운영 credential 대신 namespace를 보완한 sandbox와 로컬 수신자를 사용한다', () => {
  const result = spawnSync('python3', ['-c', `
import importlib.util
import json
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('local_config', 'local/shared/scripts/k8s_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
server = config.module('airflow')
keys = ('MAIL_API_URL', 'MAIL_API_KEY', 'MAIL_API_SYSTEM_ID', 'MAIL_API_KNOX_ID',
        'AIRFLOW_FAILURE_ALERT_EMAIL_FROM', 'AIRFLOW_FAILURE_ALERT_EMAIL_TO')
mail = dict(MAIL_API_URL='http://adfs:9000/mail/send', MAIL_API_KEY='dummy-ticket',
            MAIL_API_SYSTEM_ID='plane', MAIL_API_KNOX_ID='dummy-knox-id')
creds = {key: 'fixture' for key in ('AIRFLOW_DB_PASSWORD', 'AIRFLOW_OIDC_CLIENT_SECRET',
         'AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_WEBSERVER_SECRET_KEY', 'AIRFLOW_FERNET_KEY', 'AIRFLOW_TRIGGER_TOKEN')}
with patch.object(config, 'module', return_value=server), \\
     patch.object(server, 'read_env', return_value={key: 'server-only' for key in keys}), \\
     patch.object(config, 'read_env', return_value=mail), \\
     patch.object(config, 'settings', return_value={'LOCAL_AIRFLOW_FAILURE_ALERT_EMAIL_TO': 'operator@localhost.test'}):
    settings = config.airflow_settings(creds)
print(json.dumps({key: settings[key] for key in keys}))
`], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    MAIL_API_URL: 'http://adfs.tailwind-local.svc.cluster.local:9000/mail/send',
    MAIL_API_KEY: 'dummy-ticket', MAIL_API_SYSTEM_ID: 'plane', MAIL_API_KNOX_ID: 'dummy-knox-id',
    AIRFLOW_FAILURE_ALERT_EMAIL_FROM: 'airflow@localhost.test', AIRFLOW_FAILURE_ALERT_EMAIL_TO: 'operator@localhost.test',
  });
});

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
  for (const app of ['portal', 'minio', 'keycloak', 'headlamp', 'adfs_dummy']) {
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
  const owners = { portal: ['api', 'edge-nginx', 'web'], minio: ['minio'], keycloak: ['keycloak'],
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

test('MinIO 소유권 분리 후에도 기존 로컬 PVC·PV·데이터 경로는 유지한다', () => {
  const items = render('local/minio/k8s');
  const claim = items.find(item => item.kind === 'PersistentVolumeClaim');
  const volume = items.find(item => item.kind === 'PersistentVolume');
  assert.equal(claim.metadata.namespace, 'tailwind-local');
  assert.equal(claim.metadata.name, 'minio-data');
  assert.equal(claim.spec.volumeName, 'tailwind-local-minio');
  assert.equal(volume.spec.local.path, '/data/local-runtime/minio');
  assert.deepEqual(volume.spec.claimRef, {name: 'minio-data', namespace: 'tailwind-local'});
  assert.equal(volume.spec.persistentVolumeReclaimPolicy, 'Retain');
});

test('platform 집계는 Portal·mock·기존 token Headlamp 없이 공통 기반과 저장소·SSO만 포함한다', () => {
  const items = render('local/shared/k8s/platform');
  assert.deepEqual(items.filter(item => item.kind === 'Deployment').map(item => item.metadata.name).sort(),
    ['keycloak', 'minio', 'traefik']);
  assert.ok(!items.some(item => item.kind === 'Job' && item.metadata.name.startsWith('portal')));
  const local = items.find(item => item.kind === 'Deployment' && item.metadata.name === 'keycloak');
  const server = render('deploy/keycloak/k8s').find(item => item.kind === 'Deployment' && item.metadata.name === 'keycloak');
  assert.deepEqual(local.spec.template.spec.containers[0].startupProbe,
    server.spec.template.spec.containers[0].startupProbe);
  assert.deepEqual(local.spec.template.spec.containers[0].args, ['start', '--import-realm']);
});
