# API server OIDC 인증

[가이드 홈](../README.md#클러스터) · [CP1~3 셋업](control-plane.md) · [Headlamp 인증](../../../headlamp/docs/02-authentication.md)

**목적:** Kubernetes API server가 Keycloak이 발급한 OIDC 토큰을 신뢰하도록 모든 제어면에 issuer·client ID·claim 매핑·CA를 반영합니다.
Keycloak은 사용자를 인증하고 API server는 그 토큰을 신뢰할지 판단합니다. 이 설정이 없으면 OIDC 로그인 후에도 자원 조회가 실패합니다.

**준비물:**

- 앱이 정한 인증 계약: issuer, audience(client ID), username·groups claim과 prefix, 서명 알고리즘. 현재 사용 앱인 Headlamp의 계약은 [Headlamp 인증](../../../headlamp/docs/02-authentication.md)에 있고, 3단계의 프로그램에 그 값이 들어 있습니다.
- 운영 issuer: Headlamp env의 `HEADLAMP_OIDC_ISSUER_URL`. 1단계의 `make -s headlamp-setup-env` 출력에서 읽으며 [서비스 원본](../infrastructure/services.md)의 업무 realm OIDC issuer와 같아야 합니다.
- 사내 CA 묶음 PEM 한 파일: 관리 호스트의 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`. 없으면 [사내 CA 묶음](../../../README.md#사내-ca-묶음)의 명령으로 만듭니다. PFX·사이트 개인키는 제어면으로 옮기지 않습니다.
- 각 제어면의 SSH 접속과 비밀번호 없는 sudo. 확인 방법은 [노드 SSH](../infrastructure/access.md#노드-ssh)에 있습니다.

**실행 위치:** 단계마다 적습니다. `kubectl`·`make` 블록은 관리 호스트의 저장소 루트에서 실행합니다. `/etc/kubernetes` 파일을 다루는 블록은 대상 제어면에서 실행하는 명령이며 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 블록 전체를 그 제어면의 셸에 전달합니다. 블록마다 새 셸입니다.

**자리표시:** `<제어면>`은 1단계에서 조회한 제어면 노드 이름 하나, `<issuer>`는 운영 issuer, `<백업 파일>`은 3단계 프로그램이 출력한 `백업 파일:` 경로입니다.

SSO 주소를 바꿀 때는 앱 env와 모든 API server의 issuer·CA를 함께 맞춥니다. 다른 인증 공급자 설정은 보존합니다.

| 현재 상황 | 진행 방법 |
| --- | --- |
| kubeadm이고 OIDC 설정이 없음 | 1 → 제어면마다 2 → 3 → 4 → 마지막에 6 |
| 같은 계약의 OIDC 설정이 일부 또는 모두 있음 | 위와 같습니다. 3단계 프로그램은 값이 같은 옵션을 건너뛰고 빠진 것만 추가하며, 모두 있으면 `변경 없음`으로 끝납니다 |
| `--authentication-config` 사용 중 | 1 → 2 → 5 → 6. 3단계 프로그램은 이 옵션을 발견하면 바꾸지 않고 멈춥니다 |
| 다른 issuer·client의 `--oidc-*` 설정이 있음 | 3단계 프로그램이 바꾸지 않고 멈춥니다. 멈추고 보고합니다. 기존 옵션을 지우거나 덮어쓰지 않습니다 |
| 1단계에서 `/etc/kubernetes/manifests/kube-apiserver.yaml`이 없음(관리형 클러스터·k3s·RKE2 등) | 이 문서의 대상이 아닙니다. 멈추고 보고합니다. 그 경로에 새 파일을 만들지 않습니다 |

API server의 재시작은 [승인] 단계입니다. 제어면을 한 대씩 진행하고, 4단계의 조회가 성공한 뒤에 다음 제어면으로 갑니다.

## 1. 계약과 기존 인증 확인

[조회] 관리 호스트에서 버전, API server Pod가 있는 제어면 노드, 현재 인증 옵션, 운영 issuer를 조회합니다. Headlamp가 저장소 밖 env를 쓰면 마지막 명령에 `HEADLAMP_ENV=<경로>`를 붙입니다.

```bash
kubectl --context "<context>" version
kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver -o wide
kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver \
  -o jsonpath='{.items[*].spec.containers[0].command}' | tr ',' '\n' | grep -E -- '--(oidc-|authentication-config)' | sort | uniq -c
make -s headlamp-setup-env
```

**기대 결과:** 둘째 명령의 `NODE` 열이 제어면 노드 이름(`<제어면>`)입니다. 셋째 명령은 인증 옵션마다 그 옵션을 가진 API server 수를 출력하며, 출력이 없으면 옵션이 없는 상태입니다. 마지막 명령의 `HEADLAMP_OIDC_ISSUER_URL` 값이 `<issuer>`이고 `HEADLAMP_OIDC_CLIENT_ID`는 `headlamp`입니다.
`kubectl`이 실패하면 [Kubernetes API](../infrastructure/access.md#kubernetes-api) 절로 접속을 확인합니다. `HEADLAMP_OIDC_CLIENT_ID`가 `headlamp`가 아니면 3단계 프로그램의 `('--oidc-client-id', 'headlamp')` 줄에서 `headlamp`를 그 값으로 바꿔 실행합니다.

[조회] 각 제어면에서 manifest와 형식을 확인합니다. 실행 위치는 `<제어면>`이며 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

```bash
sudo test -f /etc/kubernetes/manifests/kube-apiserver.yaml && echo 'kubeadm manifest 있음'
sudo grep -nE -- '--(oidc-|authentication-config)' /etc/kubernetes/manifests/kube-apiserver.yaml
sudo grep -cE '^    - kube-apiserver$|^    volumeMounts:$|^  volumes:$' /etc/kubernetes/manifests/kube-apiserver.yaml
```

**기대 결과:** `kubeadm manifest 있음`이 출력됩니다. 둘째 명령의 출력이 없으면 인증 옵션이 없는 상태입니다. 셋째 명령은 `3`을 출력합니다(3단계 프로그램이 기준으로 삼는 세 줄).

**실패 확인:**

- `kubeadm manifest 있음`이 나오지 않으면 위 표의 마지막 행입니다.
- 셋째 명령이 `3`이 아니면 kubeadm이 쓴 형식이 아닙니다. 3단계 프로그램도 같은 이유로 멈추므로 진행하지 않고 그 출력을 보고합니다.
- 옵션이 이미 있으면 위 표에서 해당하는 행을 따릅니다. 기존 `--oidc-*`가 다른 issuer·client에 연결돼 있으면 덮어쓰지 않습니다. 인증 통합이 끝날 때까지 앱 배포만으로 로그인이 완성된 것으로 보지 않습니다.

## 2. CA 파일 배치 — 제어면 한 대

이 절차는 사내 CA로 서명된 issuer 기준입니다. 공인 CA를 쓰는 issuer에는 `--oidc-ca-file`과 CA 마운트가 필요 없고 3단계 프로그램은 그 구성을 만들지 않으므로, 그 경우에는 멈추고 보고합니다.

1. [변경] 관리 호스트의 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`을 [노드 SSH](../infrastructure/access.md#노드-ssh)의 파일 전송 방법으로 `<제어면>`의 `/tmp/keycloak-ca-bundle.pem`에 복사합니다. 관리 호스트의 파일과 환경변수는 다른 서버에 자동으로 전달되지 않습니다.
2. [변경] `<제어면>`에서 API server가 읽을 위치에 설치하고 내용을 확인합니다.
   ```bash
   sudo install -d -m 0755 /etc/kubernetes/oidc
   sudo install -m 0644 /tmp/keycloak-ca-bundle.pem /etc/kubernetes/oidc/keycloak-ca-bundle.pem
   rm -f /tmp/keycloak-ca-bundle.pem
   openssl crl2pkcs7 -nocrl -certfile /etc/kubernetes/oidc/keycloak-ca-bundle.pem |
     openssl pkcs7 -print_certs -noout
   ```

**기대 결과:** 사내 CA 구성에서는 루트·중간 CA의 `subject`와 `issuer`가 표시됩니다.
API server 컨테이너에도 이 파일이 보여야 하므로 3단계에서 `/etc/kubernetes/oidc`를 마운트합니다. 앱 namespace의 ConfigMap 등록만으로는 부족합니다.

## 3. oidc 옵션 반영 — kubeadm static Pod, 제어면 한 대

[승인] `<제어면>`의 `/etc/kubernetes/manifests/kube-apiserver.yaml`을 바꿉니다. 파일이 바뀌면 kubelet이 그 제어면의 API server를 다시 시작합니다. 제어면이 한 대뿐이면 다시 시작하는 동안 API 요청이 중단되고, 여러 대면 다른 제어면이 요청을 받습니다. 대상 제어면, 아래 블록, 이 영향을 보여 주고 승인받은 뒤 실행합니다.

아래 블록에서 `<issuer>`만 실제 값으로 바꿉니다. 프로그램은 다음과 같이 동작합니다.

- kubeadm이 쓴 manifest를 전제로 합니다. command의 첫 항목 `    - kube-apiserver`(공백 4칸), 컨테이너의 `    volumeMounts:`(공백 4칸), Pod의 `  volumes:`(공백 2칸) 줄이 각각 하나씩 있고 그 아래 목록이 같은 들여쓰기의 `- `로 시작해야 합니다. 하나라도 다르면 쓰지 않고 멈춥니다.
- `--oidc-*` 옵션 8개를 `- kube-apiserver` 줄 바로 아래에 넣습니다. 같은 이름의 옵션이 같은 값으로 있으면 넣지 않고, 다른 값으로 있거나 `--authentication-config`가 있으면 쓰지 않고 멈춥니다.
- `keycloak-oidc-ca` 항목(hostPath `/etc/kubernetes/oidc`, type `Directory`, 읽기 전용 마운트 `/etc/kubernetes/oidc`)을 `volumeMounts:`와 `volumes:` 아래에 각각 없을 때만 넣습니다.
- 기존 줄은 지우거나 고치지 않습니다. 결과를 `/etc/kubernetes/backup/`의 임시 파일에 쓰고, 그 파일이 기존 줄을 순서대로 모두 담고 있을 때만 원본을 `/etc/kubernetes/backup/kube-apiserver.<시각>.yaml`로 백업한 뒤 manifest를 교체합니다. 노드에 PyYAML이 있으면 YAML 해석과 옵션·마운트 확인도 통과해야 교체합니다. 백업은 kubelet이 읽는 manifests 폴더 밖에 둡니다.
- 다시 실행해도 됩니다. 넣을 것이 없으면 `변경 없음`을 출력하고 파일과 백업을 만들지 않습니다.

실행 위치는 `<제어면>`이며 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 블록 전체를 전달합니다.

```bash
sudo python3 - '<issuer>' <<'PY'
import os
import shutil
import sys
import time

manifest = '/etc/kubernetes/manifests/kube-apiserver.yaml'
backups = '/etc/kubernetes/backup'
ca_file = '/etc/kubernetes/oidc/keycloak-ca-bundle.pem'
issuer = sys.argv[1] if len(sys.argv) > 1 else ''
flags = [
    ('--oidc-issuer-url', issuer),
    ('--oidc-client-id', 'headlamp'),
    ('--oidc-username-claim', 'sub'),
    ('--oidc-username-prefix', 'headlamp:'),
    ('--oidc-groups-claim', 'groups'),
    ('--oidc-groups-prefix', 'headlamp:'),
    ('--oidc-signing-algs', 'RS256'),
    ('--oidc-ca-file', '/etc/kubernetes/oidc/keycloak-ca-bundle.pem'),
]
mount = ['    - mountPath: /etc/kubernetes/oidc', '      name: keycloak-oidc-ca', '      readOnly: true']
volume = ['  - hostPath:', '      path: /etc/kubernetes/oidc', '      type: Directory', '    name: keycloak-oidc-ca']


def stop(reason):
    sys.exit('중단: ' + reason + ' manifest를 바꾸지 않았습니다.')


def anchor(line, item):
    """kubeadm 형식의 기준 줄이 하나뿐이고 바로 아래가 같은 들여쓰기의 목록 항목인지 확인한다."""
    found = [index for index, value in enumerate(original) if value.rstrip() == line]
    if len(found) != 1 or not ''.join(original[found[0] + 1:found[0] + 2]).startswith(item):
        stop('`' + line + '` 줄과 그 아래 `' + item + '` 항목을 찾지 못했습니다. kubeadm이 만든 형식이 아닙니다.')
    return found[0]


def listed(start, indent):
    """start 줄 아래 목록에 keycloak-oidc-ca 항목이 이미 있는지 본다."""
    for value in original[start + 1:]:
        if not value.startswith((' ' * indent + '- ', ' ' * (indent + 2))):
            return False
        if value.strip().lstrip('- ') == 'name: keycloak-oidc-ca':
            return True
    return False


if not issuer.startswith('https://') or '<' in issuer or ' ' in issuer:
    stop('첫 인자에 실제 issuer URL(https://...)을 지정하세요.')
if not os.path.isfile(ca_file):
    stop(ca_file + ' 파일이 없습니다. 2단계를 먼저 실행하세요.')
with open(manifest, encoding='utf-8') as source:
    original = source.read().split('\n')
command = anchor('    - kube-apiserver', '    - ')
mounts = anchor('    volumeMounts:', '    - ')
volumes = anchor('  volumes:', '  - ')
if not command < mounts < volumes:
    stop('command·volumeMounts·volumes의 순서가 kubeadm 형식과 다릅니다.')

# 이미 있는 옵션은 건드리지 않는다. 같은 이름이 다른 값이면 덮어쓰지 않고 멈춘다.
existing = {}
for value in original:
    name, _, current = value.strip()[2:].strip().strip('\'"').partition('=')
    if value.strip().startswith('- ') and name.startswith('--'):
        existing[name] = current
if '--authentication-config' in existing:
    stop('--authentication-config를 사용 중입니다. 5단계의 방식으로 반영하세요.')
adding = []
for name, wanted in flags:
    if name not in existing:
        text = name + '=' + wanted
        adding.append('    - ' + ("'" + text + "'" if text.endswith(':') else text))
    elif existing[name] != wanted:
        stop(name + ' 옵션이 다른 값으로 이미 있습니다: ' + existing[name] + '.')
has_mount, has_volume = listed(mounts, 4), listed(volumes, 2)
result = []
for index, value in enumerate(original):
    result.append(value)
    if index == command:
        result += adding
    elif index == mounts and not has_mount:
        result += mount
    elif index == volumes and not has_volume:
        result += volume
if result == original:
    print('변경 없음: OIDC 옵션과 CA 마운트가 이미 있습니다.')
    sys.exit(0)

# 임시 파일에 쓴 결과가 기존 줄을 순서대로 모두 담고 있을 때만 manifest를 교체한다.
os.makedirs(backups, mode=0o700, exist_ok=True)
stamp = time.strftime('%Y%m%d%H%M%S')
draft = os.path.join(backups, 'kube-apiserver.' + stamp + '.new')
with open(draft, 'w', encoding='utf-8') as target:
    target.write('\n'.join(result))
with open(draft, encoding='utf-8') as check:
    written = check.read().split('\n')
rest = iter(written)
kept = all(value in rest for value in original)
entries = sum(1 for value in written if value.strip().lstrip('- ') == 'name: keycloak-oidc-ca')
try:
    import yaml
    pod = yaml.safe_load('\n'.join(written))['spec']
    valid = (all(name + '=' + wanted in pod['containers'][0]['command'] for name, wanted in flags)
             and any(item.get('name') == 'keycloak-oidc-ca' and item.get('mountPath') == '/etc/kubernetes/oidc'
                     for item in pod['containers'][0]['volumeMounts'])
             and any(item.get('name') == 'keycloak-oidc-ca' and (item.get('hostPath') or {}).get('path') == '/etc/kubernetes/oidc'
                     for item in pod['volumes']))
except ImportError:
    valid = True  # PyYAML이 없는 노드는 위의 줄 보존 검사만 한다.
except Exception:
    valid = False
if not (kept and entries == 2 and valid):
    os.remove(draft)
    stop('결과가 기존 줄을 보존하지 않았거나 올바른 YAML이 아닙니다.')
backup = os.path.join(backups, 'kube-apiserver.' + stamp + '.yaml')
shutil.copy2(manifest, backup)
state = os.stat(manifest)
os.chmod(draft, state.st_mode & 0o7777)
os.chown(draft, state.st_uid, state.st_gid)
os.replace(draft, manifest)
print('추가한 옵션 ' + str(len(adding)) + '개, volumeMounts 항목 추가 ' + ('안 함' if has_mount else '함')
      + ', volumes 항목 추가 ' + ('안 함' if has_volume else '함'))
print('백업 파일: ' + backup)
print('kube-apiserver manifest 갱신 완료. kubelet이 이 제어면의 API server를 다시 시작합니다.')
PY
```

**성공:** `kube-apiserver manifest 갱신 완료`와 `백업 파일: /etc/kubernetes/backup/kube-apiserver.<시각>.yaml`이 출력됩니다. 이미 반영된 제어면은 `변경 없음: OIDC 옵션과 CA 마운트가 이미 있습니다.`를 출력합니다. 출력된 백업 파일 경로를 4단계의 복구에 씁니다.

**실패:** `중단:`으로 시작하는 줄이나 Python 오류로 끝나면 manifest는 바뀌지 않았습니다. manifest를 손으로 고치지 않습니다.

| 출력 | 조치 |
| --- | --- |
| `첫 인자에 실제 issuer URL` | `<issuer>`를 1단계의 `HEADLAMP_OIDC_ISSUER_URL` 값으로 바꿔 다시 실행 |
| `keycloak-ca-bundle.pem 파일이 없습니다` | 2단계를 실행한 뒤 다시 실행 |
| `--authentication-config를 사용 중입니다` | [5단계](#5-authenticationconfiguration-방식인-경우) |
| `옵션이 다른 값으로 이미 있습니다` | 다른 issuer·client의 설정입니다. 멈추고 보고합니다. 기존 옵션을 지우거나 덮어쓰지 않습니다 |
| `kubeadm이 만든 형식이 아닙니다`, `순서가 kubeadm 형식과 다릅니다`, `결과가 기존 줄을 보존하지 않았거나` | 멈추고 그 출력과 1단계의 조회 결과를 보고합니다 |

kubeadm이 manifest를 다시 만들면(`kubeadm upgrade` 등) 이 옵션과 마운트가 사라집니다. 업그레이드 뒤에는 6단계의 조회로 확인하고, 빠졌으면 2~4단계를 다시 실행합니다. 재생성 후에도 유지하려면 `kube-system`의 `kubeadm-config` ConfigMap에 있는 ClusterConfiguration의 `apiServer.extraArgs`·`extraVolumes`에도 같은 값을 기록합니다.

## 4. 재기동 확인과 복구 — 제어면 한 대

[조회] 관리 호스트에서 `<제어면>`의 API server가 새 옵션으로 다시 떴는지 기다립니다. 3단계가 `변경 없음`이었어도 실행합니다.

```bash
for attempt in $(seq 1 60); do
  kubectl --context "<context>" -n kube-system get pod "kube-apiserver-<제어면>" \
    -o jsonpath='{.spec.containers[0].command}' 2>/dev/null | grep -q -- '--oidc-issuer-url=' && break
  sleep 5
done
kubectl --context "<context>" -n kube-system wait --for=condition=Ready "pod/kube-apiserver-<제어면>" --timeout=300s
kubectl --context "<context>" get --raw='/readyz'
kubectl --context "<context>" get node "<제어면>"
kubectl --context "<context>" -n kube-system get pod "kube-apiserver-<제어면>" \
  -o jsonpath='{range .spec.containers[0].command[*]}{@}{"\n"}{end}' | grep -c -- '--oidc-'
```

**성공:** `pod/kube-apiserver-<제어면> condition met`, `ok`, 노드 `STATUS`가 `Ready`, 마지막 줄이 `8`입니다. 이 결과가 나온 뒤에 다음 제어면의 2단계로 갑니다. 이 조회만으로 OIDC 로그인 성공이 검증되지는 않습니다.

**실패:** 5분 안에 위 결과가 나오지 않으면 다음 제어면으로 가지 않고 아래 순서로 복구합니다. 제어면이 한 대뿐이면 API가 응답하지 않아 `kubectl`도 실패합니다.

1. [조회] `<제어면>`에서 원인과 백업 파일을 봅니다. 접근 방법은 [노드 SSH](../infrastructure/access.md#노드-ssh)입니다.
   ```bash
   sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock ps -a --name kube-apiserver
   sudo journalctl -u kubelet --since '10 min ago' --no-pager | tail -n 40
   sudo ls -1t /etc/kubernetes/backup/
   ```
2. [승인] `<제어면>`에서 3단계가 출력한 백업 파일로 manifest를 되돌립니다. kubelet이 API server를 이전 설정으로 다시 시작하며, 3단계에서 승인받은 같은 제어면의 재시작 범위입니다.
   ```bash
   sudo cp -p <백업 파일> /etc/kubernetes/manifests/kube-apiserver.yaml
   ```
3. [조회] 관리 호스트에서 복구를 확인한 뒤 멈추고 1번의 출력과 함께 보고합니다.
   ```bash
   kubectl --context "<context>" -n kube-system wait --for=condition=Ready "pod/kube-apiserver-<제어면>" --timeout=300s
   kubectl --context "<context>" get --raw='/readyz'
   kubectl --context "<context>" get node "<제어면>"
   ```
   성공: `condition met`, `ok`, 노드 `Ready`.

## 5. AuthenticationConfiguration 방식인 경우

manifest에 `--authentication-config=<파일>`이 있는 클러스터는 `--oidc-*` 옵션을 함께 쓸 수 없으므로 그 인증 파일에 issuer·audience·CA와 claim 매핑을 반영합니다. 지원 API 버전은 실행 중인 Kubernetes 버전에 맞춥니다.
기존 issuer 항목을 보존하고, 같은 issuer가 이미 있으면 그 항목의 audience·매핑이 다른 앱에 주는 영향을 먼저 확인합니다.

```yaml
# 기존 jwt 항목 안에 합칠 매핑의 형식 예시(Headlamp 계약). 전체 인증 파일이 아닙니다.
claimMappings:
  username:
    claim: sub
    prefix: 'headlamp:'
  groups:
    claim: groups
    prefix: 'headlamp:'
```

- `issuer.url`은 공개 issuer, `issuer.audiences`에는 앱의 client ID를 사용합니다.
- 사내 CA는 `issuer.certificateAuthority`에 PEM **내용**을 넣습니다. 파일 경로 필드가 아닙니다.
- 이 방식에는 고정된 명령 블록이 없습니다. 인증 파일의 기존 내용에 따라 합칠 위치가 달라지므로, 각 제어면에서 [조회]한 기존 파일과 합친 결과의 차이를 [승인] 요청에 함께 보여 줍니다.
- [승인] 인증 파일을 manifests 폴더 밖(`/etc/kubernetes/backup/`)에 백업한 뒤 새 내용을 비대화형으로 써서 교체합니다. 모든 API server에 같은 내용을 적용하며, 한 대씩 적용하고 4단계의 `wait`·`/readyz`·노드 조회가 성공한 뒤 다음 제어면으로 갑니다. 실패하면 백업 파일을 같은 경로로 되돌립니다.
- 세부 스키마는 [공식 인증 설정](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#authentication-configuration-from-a-file)을 따릅니다.

## 6. 완료 확인 — 관리 호스트

[조회] 모든 제어면에 적용한 뒤 관리자 kubeconfig로 확인합니다. LB 뒤의 한 서버만 정상일 수 있으므로 API server별 적용값을 함께 봅니다.

```bash
kubectl --context "<context>" get --raw='/readyz'
kubectl --context "<context>" get nodes
kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver -o wide
kubectl --context "<context>" -n kube-system get pods -l component=kube-apiserver \
  -o jsonpath='{.items[*].spec.containers[0].command}' | tr ',' '\n' | grep -- '--oidc-' | sort | uniq -c
```

**기대 결과:** `readyz`가 `ok`이고 노드 목록이 조회되며 API server Pod가 모두 `Running`입니다. 마지막 명령은 옵션 8줄을 출력하고 줄마다 앞의 숫자가 제어면 수와 같습니다. 이 결과만으로 OIDC 인증 성공이 검증되지는 않습니다.

| 확인 항목 | 기대 결과 |
| --- | --- |
| 적용 범위 | 모든 제어면에 적용. 일부 서버만 적용한 상태가 아님 |
| issuer·client ID | 앱 계약의 realm URL·client ID와 일치 |
| claim·prefix | 앱 계약과 일치. 그룹 경로의 슬래시는 토큰 값에 포함됨 |
| CA | 모든 API server에서 Keycloak discovery·JWKS의 DNS·HTTPS 검증 가능 |
| 기존 관리자 접속 | `/readyz`는 `ok`, 노드 목록 조회 성공 |

**완료 기준:** 모든 API server에 같은 인증 계약이 적용됐고 기존 관리자 접속이 정상입니다. 적용 결과는 [서버 적용 대기 작업](../infrastructure/pending.md)의 해당 행에 반영합니다.

## CA 교체

CA를 교체하면 새 CA 묶음으로 이 문서의 절차와 앱 쪽 CA 설정을 함께 갱신합니다. 옵션과 마운트가 이미 있으면 3단계는 `변경 없음`으로 끝나 API server가 다시 시작되지 않으므로, 제어면 한 대씩 다음 순서로 진행합니다.

1. [변경] 2단계로 새 묶음을 `<제어면>`의 `/etc/kubernetes/oidc/keycloak-ca-bundle.pem`에 둡니다.
2. [승인] `<제어면>`에서 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 API server 컨테이너를 멈춥니다. kubelet이 곧바로 다시 시작하며 새 CA 파일을 읽습니다. 영향은 3단계와 같습니다.
   ```bash
   sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock stop \
     "$(sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock ps --name kube-apiserver -q)"
   ```
3. [조회] 4단계의 첫 블록으로 확인합니다. `kubectl --context "<context>" -n kube-system get pod "kube-apiserver-<제어면>"`의 `RESTARTS`가 늘고 `READY`가 `1/1`이면 다음 제어면으로 갑니다.

## 다음 단계

앱 가이드에서 실제 로그인과 그룹별 권한을 확인합니다. Headlamp는 [배포 후 확인](../../../headlamp/README.md#c-배포-후-확인)입니다.

공식 참고: [Kubernetes OIDC](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens),
[kubeadm 제어면 구성](https://kubernetes.io/docs/reference/setup-tools/kubeadm/implementation-details/).
