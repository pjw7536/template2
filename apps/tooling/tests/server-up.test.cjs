const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const yaml = require('js-yaml');

test('Keycloak·Airflow 기동은 기존 진입점과 Secret을 보존하고 namespace 권한을 먼저 준비한다', () => {
  const result = spawnSync('python3', ['-m', 'unittest', 'discover', '-s', 'deploy/shared/tests', '-v'], {
    cwd: path.resolve(__dirname, '../../..'), encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('실제 Keycloak 렌더에서 VIP 배치 변경은 Traefik에만 적용되고 443 직결을 유지한다', () => {
  const root = path.resolve(__dirname, '../../..');
  const rendered = spawnSync('kubectl', ['kustomize', 'deploy/keycloak/k8s'], { cwd: root, encoding: 'utf8' });
  assert.equal(rendered.status, 0, rendered.stderr);
  const resources = yaml.loadAll(rendered.stdout);
  const source = resources.find(r => r.kind === 'Deployment' && r.metadata.name === 'traefik');
  const code = `
import json, sys, importlib.util
spec = importlib.util.spec_from_file_location('routing', 'deploy/shared/ingress/routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)
resources = json.load(sys.stdin)
source = routing.controller(resources)
hostname = source['spec']['template']['spec']['nodeSelector']['kubernetes.io/hostname']
nodes = [{'metadata': {'name': name, 'labels': {'kubernetes.io/hostname': label}}, 'spec': {},
          'status': {'addresses': [{'type': 'InternalIP', 'address': ip}], 'conditions': [{'type': 'Ready', 'status': 'True'}]}}
         for name, label, ip in [('first-node', hostname, '192.0.2.10'), ('second-node', 'second-worker', '192.0.2.20')]]
updated = routing.place_vip_backends(source, source, ['192.0.2.10', '192.0.2.20'], nodes, [])
print(json.dumps([updated if item is source else item for item in resources]))
`;
  const patched = spawnSync('python3', ['-c', code], { cwd: root, input: JSON.stringify(resources), encoding: 'utf8' });
  assert.equal(patched.status, 0, patched.stderr);
  const result = JSON.parse(patched.stdout);
  const controller = result.find(r => r.kind === 'Deployment' && r.metadata.name === 'traefik');
  assert.equal(controller.spec.replicas, 2);
  assert.deepEqual(controller.spec.template.spec.containers, source.spec.template.spec.containers);
  assert.equal(controller.spec.template.spec.containers[0].ports.find(p => p.name === 'websecure').hostPort, 443);
  assert.deepEqual(result.filter(r => !(r.kind === 'Deployment' && r.metadata.name === 'traefik')),
    resources.filter(r => !(r.kind === 'Deployment' && r.metadata.name === 'traefik')));
  assert.ok(!result.some(r => r.kind === 'Service' && r.spec.type === 'NodePort'));
});
