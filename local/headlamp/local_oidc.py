"""서버 Headlamp chart와 OIDC 계약에 로컬 주소·CA·테스트 계정만 적용합니다."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlencode

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared/scripts'))
from k8s import KUBE, apply, resources, rollout, run, secret
from k8s_config import CLUSTER, ROOT, RUNTIME, module, write_private

ISSUER = 'https://sso.localhost:8443/realms/local-platform'
URL = 'https://localhost:8443/headlamp/'
CA = RUNTIME / 'headlamp-tls/ca.crt'
KEY = RUNTIME / 'headlamp-tls/tls.key'
CONTROL_PLANE = CLUSTER + '-control-plane'


def values(address='127.0.0.1'):
    """서버의 OIDC 설정 검사를 재사용하고 callback의 로컬 포트만 보정합니다."""
    env = dict(HEADLAMP_REGISTRY='ghcr.io', IMAGE_PULL_SECRET='', HEADLAMP_HOST='headlamp.localhost',
               HEADLAMP_TLS_SECRET='', HEADLAMP_OIDC_ISSUER_URL=ISSUER,
               HEADLAMP_OIDC_CLIENT_ID='headlamp', HEADLAMP_OIDC_SECRET='headlamp-oidc',
               HEADLAMP_OIDC_CA_CONFIGMAP='headlamp-ca')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'headlamp.env'
        path.write_text(''.join(f'{key}={value}\n' for key, value in env.items()))
        result = module('headlamp').settings(path)
    for entry in result['env']:
        if entry['name'] == 'OIDC_CALLBACK_URL':
            entry['value'] = URL + 'oidc-callback'
    result['hostAliases'] = [{'ip': address, 'hostnames': ['sso.localhost']}]
    result['ingress']['hosts'][0]['host'] = 'localhost'
    result['ingress']['tls'] = [{'secretName': 'headlamp-tls', 'hosts': ['localhost']}]
    # 서버 원본의 관리자 Group binding 이름과 분리해 기존 서버 리소스와 충돌하지 않습니다.
    result['extraManifests'] = [yaml.safe_dump({
        'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding',
        'metadata': {'name': 'local-headlamp-admin'},
        'subjects': [{'kind': 'Group', 'name': 'headlamp:/headlamp-admins',
                      'apiGroup': 'rbac.authorization.k8s.io'}],
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': 'cluster-admin'}})]
    return result


def render(address='127.0.0.1'):
    """서버와 동일한 chart SHA-256·values로 Secret 없는 manifest를 렌더합니다."""
    deploy = module('headlamp')
    deploy.verify_chart(deploy.chart_path())
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'values.json'
        path.write_text(json.dumps(values(address)))
        flags = ['--namespace', 'headlamp', '-f', ROOT / 'deploy/headlamp/helm/values.yaml', '-f', path]
        output = run(['helm', 'template', 'local-headlamp', deploy.chart_path(), *flags], quiet=True)
        return list(filter(None, yaml.safe_load_all(output)))


def tls_prepare():
    """로컬 전용 인증서는 재사용하고 호스트 신뢰 저장소는 변경하지 않습니다."""
    if CA.exists() != KEY.exists():
        raise ValueError('로컬 TLS 파일 일부가 없습니다. headlamp-tls 백업을 복원하세요.')
    if not CA.exists():
        CA.parent.mkdir(parents=True, mode=0o700)
        run(['openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '3650',
             '-subj', '/CN=tailwind-local', '-addext', 'basicConstraints=critical,CA:TRUE',
             '-addext', 'subjectAltName=DNS:localhost,DNS:sso.localhost',
             '-keyout', KEY, '-out', CA], quiet=True, sensitive=True)
        KEY.chmod(0o600)
    run(['openssl', 'x509', '-in', CA, '-checkend', '86400', '-noout'], quiet=True)
    for namespace in ('tailwind-local', 'headlamp'):
        secret(namespace, 'headlamp-tls', {'tls.crt': CA.read_text(), 'tls.key': KEY.read_text()})
    apply([{'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'headlamp-ca', 'namespace': 'headlamp'},
            'data': {'ca.crt': CA.read_text()}}])


def ingress_up():
    """같은 HTTPS issuer를 브라우저·Headlamp·API server가 모두 사용할 수 있게 합니다."""
    items = resources('local/shared/k8s/base')
    controller = next(item for item in items if item['kind'] == 'Deployment')
    pod = controller['spec']['template']['spec']
    pod['nodeSelector'] = {'kubernetes.io/hostname': CONTROL_PLANE}
    pod['tolerations'] = [{'key': 'node-role.kubernetes.io/control-plane', 'operator': 'Exists', 'effect': 'NoSchedule'}]
    container = pod['containers'][0]
    container['args'] = [arg.replace('namespaces=tailwind-local,airflow', 'namespaces=tailwind-local,airflow,headlamp')
                         for arg in container['args']]
    next(port for port in container['ports'] if port['name'] == 'websecure')['hostPort'] = 8443
    middleware_name = pod['volumes'][0]['configMap']['name']
    pod['volumes'][0] = {'name': 'middlewares', 'projected': {'sources': [
        {'configMap': {'name': middleware_name}},
        {'configMap': {'name': 'local-platform-tls'}}, {'secret': {'name': 'headlamp-tls'}}]}}
    apply([{'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'local-platform-tls', 'namespace': 'tailwind-local'},
            'data': {'tls.yaml': 'tls:\n  certificates:\n    - certFile: /etc/traefik/dynamic/tls.crt\n      keyFile: /etc/traefik/dynamic/tls.key\n'}}])
    role = next(item for item in items if item['kind'] == 'Role')
    binding = next(item for item in items if item['kind'] == 'RoleBinding')
    role['metadata']['namespace'] = binding['metadata']['namespace'] = 'headlamp'
    apply([role, binding, controller])
    apply([{'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress',
            'metadata': {'name': 'headlamp-sso', 'namespace': 'tailwind-local', 'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'websecure',
                'traefik.ingress.kubernetes.io/router.tls': 'true'}},
            'spec': {'ingressClassName': 'traefik', 'tls': [{'secretName': 'headlamp-tls', 'hosts': ['sso.localhost']}],
                     'rules': [{'host': 'sso.localhost', 'http': {'paths': [{'path': '/', 'pathType': 'Prefix',
                         'backend': {'service': {'name': 'keycloak', 'port': {'name': 'http'}}}}]}}]}}])
    rollout('tailwind-local', 'deployment/traefik')


def admin_client():
    """기존 공통 관리자 client를 로컬 HTTP 진입점에서 사용합니다."""
    path = ROOT / 'deploy/airflow/k8s/jobs/keycloak-client/setup_client.py'
    spec = importlib.util.spec_from_file_location('local_platform_keycloak', path)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    return client.KeycloakAdmin('http://localhost:8180', 'local-platform',
                                'local-keycloak-admin', 'local-keycloak-admin-change-me')


def realm_up(creds):
    """로컬 전용 realm·client·계정을 멱등 등록하며 기존 portal realm은 보존합니다."""
    admin = admin_client()
    realms = admin.request('GET', '/admin/realms')
    if not any(item['realm'] == 'local-platform' for item in realms):
        admin.request('POST', '/admin/realms', {'realm': 'local-platform', 'enabled': True,
                      'sslRequired': 'none', 'attributes': {'frontendUrl': ISSUER.split('/realms/')[0]}})
    else:
        realm = admin.request('GET', admin.root)
        realm['attributes'] = {**realm.get('attributes', {}), 'frontendUrl': ISSUER.split('/realms/')[0]}
        admin.request('PUT', admin.root, realm)
    definition = module('headlamp').oidc_client(values())
    found = admin.request('GET', admin.root + '/clients?' + urlencode({'clientId': 'headlamp'}))
    if not found:
        admin.request('POST', admin.root + '/clients', {**definition, 'secret': creds['HEADLAMP_OIDC_CLIENT_SECRET']})
    else:
        path = admin.root + '/clients/' + found[0]['id']
        if admin.request('GET', path + '/client-secret')['value'] != creds['HEADLAMP_OIDC_CLIENT_SECRET']:
            raise ValueError('Headlamp client secret이 기존 realm과 다릅니다. credentials.env를 복원하세요.')
        admin.request('PUT', path, definition)
    groups = admin.request('GET', admin.root + '/groups')
    if not any(item['name'] == 'headlamp-admins' for item in groups):
        admin.request('POST', admin.root + '/groups', {'name': 'headlamp-admins'})
        groups = admin.request('GET', admin.root + '/groups')
    group = next(item for item in groups if item['name'] == 'headlamp-admins')
    for username, key in [('platform-admin', 'HEADLAMP_ADMIN_PASSWORD'), ('platform-viewer', 'HEADLAMP_VIEWER_PASSWORD')]:
        users = admin.request('GET', admin.root + '/users?' + urlencode({'username': username, 'exact': 'true'}))
        if not users:
            admin.request('POST', admin.root + '/users', {'username': username, 'enabled': True,
                          'firstName': 'Local', 'lastName': username, 'email': username + '@localhost.test',
                          'credentials': [{'type': 'password', 'value': creds[key], 'temporary': False}]})
            users = admin.request('GET', admin.root + '/users?' + urlencode({'username': username, 'exact': 'true'}))
        if username == 'platform-admin':
            admin.request('PUT', admin.root + '/users/' + users[0]['id'] + '/groups/' + group['id'])


def apiserver_manifest(current):
    """다른 인증 계약은 거부하고 로컬 OIDC 플래그·CA 마운트만 병합합니다."""
    pod = current['spec']
    container = next(item for item in pod['containers'] if item['name'] == 'kube-apiserver')
    flags = {'oidc-issuer-url': ISSUER, 'oidc-client-id': 'headlamp', 'oidc-username-claim': 'sub',
             'oidc-username-prefix': 'headlamp:', 'oidc-groups-claim': 'groups', 'oidc-groups-prefix': 'headlamp:',
             'oidc-signing-algs': 'RS256', 'oidc-ca-file': '/etc/kubernetes/local-headlamp-ca.crt'}
    for arg in container['command']:
        if arg.startswith('--authentication-config') or (arg.startswith('--oidc-') and arg not in
                [f'--{key}={value}' for key, value in flags.items()]):
            raise ValueError('기존 API server에 다른 OIDC 인증 설정이 있습니다. 자동으로 교체하지 않습니다.')
    container['command'] = [arg for arg in container['command'] if not arg.startswith('--oidc-')]
    container['command'] += [f'--{key}={value}' for key, value in flags.items()]
    mount = {'name': 'local-headlamp-ca', 'mountPath': flags['oidc-ca-file'], 'readOnly': True}
    container['volumeMounts'] = [item for item in container['volumeMounts'] if item['name'] != mount['name']] + [mount]
    pod['volumes'] = [item for item in pod['volumes'] if item['name'] != mount['name']] + [
        {'name': mount['name'], 'hostPath': {'path': flags['oidc-ca-file'], 'type': 'File'}}]
    return current


def up(creds):
    """로컬 HTTPS·realm·API server 신뢰를 준비한 뒤 서버 chart를 적용합니다."""
    apply([{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'headlamp'}}])
    tls_prepare()
    ingress_up()
    realm_up(creds)
    address = run(['docker', 'inspect', '--format', '{{(index .NetworkSettings.Networks "kind").IPAddress}}',
                   CONTROL_PLANE], quiet=True).strip()
    manifest_path = '/etc/kubernetes/manifests/kube-apiserver.yaml'
    original = run(['docker', 'exec', CONTROL_PLANE, 'cat', manifest_path], quiet=True)
    current = yaml.safe_load(original)
    updated = apiserver_manifest(current)
    aliases = updated['spec'].get('hostAliases', [])
    updated['spec']['hostAliases'] = [item for item in aliases if 'sso.localhost' not in item['hostnames']] + [
        {'ip': address, 'hostnames': ['sso.localhost']}]
    run(['docker', 'cp', CA, CONTROL_PLANE + ':/etc/kubernetes/local-headlamp-ca.crt'], quiet=True)
    if yaml.safe_load(original) != updated:
        backup = RUNTIME / 'headlamp-tls/kube-apiserver.before.yaml'
        if not backup.exists():
            write_private(backup, original)
        run(['docker', 'exec', '-i', CONTROL_PLANE, 'sh', '-c',
             'cat > /etc/kubernetes/kube-apiserver.local.tmp && mv /etc/kubernetes/kube-apiserver.local.tmp /etc/kubernetes/manifests/kube-apiserver.yaml'],
            data=yaml.safe_dump(updated))
        # kubelet의 static Pod 교체와 API 재기동까지 기다립니다.
        time.sleep(10)
    for attempt in range(90):
        try:
            run([*KUBE, 'get', '--raw=/readyz'], quiet=True)
            break
        except RuntimeError:
            if attempt == 89:
                raise
            time.sleep(2)
    secret('headlamp', 'headlamp-oidc', {'OIDC_CLIENT_SECRET': creds['HEADLAMP_OIDC_CLIENT_SECRET']})
    # Helm이 아닌 apply로 기존 로컬 설치와 충돌 없이 동일 chart 결과를 적용합니다.
    apply(render(address))
    rollout('headlamp', 'deployment/headlamp')
