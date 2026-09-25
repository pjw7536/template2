const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '../../..');

function render(relative) {
  const result = spawnSync('kubectl', ['kustomize', relative], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return yaml.loadAll(result.stdout);
}

test('Keycloak 기본 스택과 전달 스택은 각 원본의 감시 범위와 TLS를 유지한다', () => {
  const exported = render('deploy/keycloak/export');
  const generated = yaml.loadAll(fs.readFileSync(path.join(root, 'deploy/keycloak/rendered/internal-keycloak-stack.yaml'), 'utf8'));
  assert.deepEqual(generated, exported);
  for (const [resources, namespaces, replicas] of [[render('deploy/keycloak/k8s'), 'etch-sso', 1], [generated, 'etch-sso,headlamp', 2]]) {
    const controller = resources.find(r => r.kind === 'Deployment' && r.metadata.name === 'traefik');
    assert.ok(controller.spec.template.spec.containers[0].args.includes(`--providers.kubernetesingress.namespaces=${namespaces}`));
    assert.equal(controller.spec.replicas, replicas);
    assert.ok(!controller.spec.template.spec.containers[0].args.some(a => a.includes('tailwind-internal')));
    const ingress = resources.find(r => r.kind === 'Ingress' && r.metadata.name === 'keycloak');
    assert.equal(ingress.metadata.annotations?.['traefik.ingress.kubernetes.io/router.entrypoints'], 'websecure');
    assert.equal(ingress.metadata.annotations?.['traefik.ingress.kubernetes.io/router.tls'], 'true');
    assert.deepEqual(ingress.spec.tls, [{ hosts: ['etch-sso.samsungds.net'], secretName: 'keycloak-tls' }]);
    assert.equal(controller.spec.template.spec.containers[0].ports.find(p => p.name === 'websecure').hostPort, 443);
    assert.ok(!resources.some(r => r.kind === 'Secret'));
  }
});

test('Portal 선택 패치는 감시 인자만 확장하며 해당 namespace 권한과 일치한다', () => {
  const keycloak = render('deploy/keycloak/k8s');
  const portal = render('deploy/portal/k8s/overlays/prod');
  const ingress = portal.find(r => r.kind === 'Ingress');
  const original = keycloak.find(r => r.kind === 'Deployment' && r.metadata.name === 'traefik');
  const patched = spawnSync('kubectl', ['patch', '--local', '-f', '-', '--type=json', '--patch-file', 'deploy/portal/k8s/overlays/prod/traefik-watch-patch.json', '-o', 'json'], { cwd: root, input: JSON.stringify(original), encoding: 'utf8' });
  assert.equal(patched.status, 0, patched.stderr);
  const controller = JSON.parse(patched.stdout);
  const expected = structuredClone(original);
  expected.spec.template.spec.containers[0].args[2] = '--providers.kubernetesingress.namespaces=etch-sso,tailwind-internal';
  assert.deepEqual(controller, expected);
  const spec = controller.spec.template.spec;
  const args = spec.containers[0].args;
  const namespaces = args.find(a => a.startsWith('--providers.kubernetesingress.namespaces=')).split('=')[1].split(',');
  assert.ok(namespaces.includes(ingress.metadata.namespace));
  assert.ok(args.includes(`--providers.kubernetesingress.ingressclass=${ingress.spec.ingressClassName}`));
  const binding = portal.find(r => r.kind === 'RoleBinding' && r.metadata.namespace === ingress.metadata.namespace);
  assert.ok(binding.subjects.some(s => s.kind === 'ServiceAccount' && s.name === spec.serviceAccountName && s.namespace === controller.metadata.namespace));
  assert.equal(binding.roleRef.kind, 'Role');
  const role = portal.find(r => r.kind === 'Role' && r.metadata.name === binding.roleRef.name && r.metadata.namespace === binding.metadata.namespace);
  for (const [group, resource] of [['', 'services'], ['', 'secrets'], ['discovery.k8s.io', 'endpointslices'], ['networking.k8s.io', 'ingresses']]) {
    assert.ok(role.rules.some(rule => rule.apiGroups.includes(group) && rule.resources.includes(resource) && ['get', 'list', 'watch'].every(v => rule.verbs.includes(v))), resource);
  }
  assert.ok(role.rules.some(rule => rule.resources.includes('ingresses/status') && rule.verbs.includes('update')));
});

test('Nginx가 API·callback·SSE·MinIO·Web에 원래 HTTPS 정보를 전달하고 직접 HTTP도 처리한다', t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-proxy-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  // 실제 프록시 설정의 upstream 주소만 격리된 컨테이너 내부 검증 서버로 바꿉니다.
  const proxy = fs.readFileSync(path.join(root, 'deploy/portal/k8s/base/nginx.conf'), 'utf8')
    .replaceAll('http://api:8000', 'http://127.0.0.1:8000')
    .replaceAll('http://minio:9000', 'http://127.0.0.1:8000')
    .replaceAll('http://web:3000', 'http://127.0.0.1:8000');
  const config = path.join(dir, 'nginx.conf');
  fs.writeFileSync(config, `events {}\nhttp { access_log off; ${proxy}\nserver { listen 8000; location / { return 200 "$http_x_forwarded_proto\\n"; } } }\n`);
  const script = `set -eu
nginx -t
nginx
for route in /api/v1/auth/login /auth/keycloak/callback/ /api/v1/assistant/turns/stream /minio/profile/test /; do
  wget -qO- --header='X-Forwarded-Proto: https' "http://127.0.0.1$route"
  wget -qO- --header='X-Forwarded-Proto: http' "http://127.0.0.1$route"
  wget -qO- "http://127.0.0.1$route"
done
`;
  const result = spawnSync('docker', ['run', '--rm', '--pull=never', '--network', 'none', '--mount', `type=bind,source=${config},target=/etc/nginx/nginx.conf,readonly`, '--entrypoint', '/bin/sh', 'nginx:1.27-alpine', '-c', script], { encoding: 'utf8', timeout: 30000 });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.stdout.trim().split('\n'), Array.from({ length: 5 }, () => ['https', 'http', 'http']).flat());
});
