# Registry 운영 작업

[Registry 가이드](../README.md)

설치·업데이트 절차는 [Registry 가이드](../README.md)에 있습니다. 이 문서는 노드의 CA 준비, push·pull 검증, 이미지·계정 관리 방법을 다룹니다.
명령은 따로 적지 않으면 관리 호스트의 저장소 루트에서 실행합니다. 노드에서 실행하는 블록은 관리 호스트에서 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)으로 전달합니다. 한 줄 블록은 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command '<블록의 명령>'`, 여러 줄 블록은 저장소 밖 파일에 저장해 `--script <블록 파일>`로 전달하며, `<노드>`는 `kubectl --context "<context>" get nodes`의 `NAME`입니다. registry Worker(`NODE_NAME`, 저장소 선언 `khplanew01`)는 관리 호스트와 같은 서버입니다.

- [노드와 관리 호스트의 CA 신뢰](#노드와-관리-호스트의-ca-신뢰)
- [수동 push·pull 시험](#수동-pushpull-시험)
- [이미지 push 규칙](#이미지-push-규칙)
- [이미지 삭제와 용량 정리](#이미지-삭제와-용량-정리)
- [push 계정 교체](#push-계정-교체)
- [저장 폴더 직접 준비](#저장-폴더-직접-준비)
- [registry 주소로 전환](#registry-주소로-전환)

## 노드와 관리 호스트의 CA 신뢰

registry 이미지를 받을 모든 노드와 이미지를 올리는 관리 호스트가 `store.etch.samsungds.net` 인증서의 발급 CA를 신뢰해야 합니다. 관리 호스트와 각 노드에서 같은 명령으로 확인합니다.

[조회] 그 호스트의 시스템 신뢰 설정으로 HTTPS 연결을 확인합니다.

```bash
curl -sS -o /dev/null -D - https://store.etch.samsungds.net/v2/
```

성공: 응답 코드가 `200`이거나 `401`이면서 `WWW-Authenticate`에 `realm="registry"`가 보입니다.

- `Could not resolve host`: 그 호스트에서 이름이 조회되지 않습니다. [DNS](../../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
- `SSL certificate problem`: 신뢰 오류입니다. 아래 등록을 수행합니다.

[변경] 신뢰 오류가 난 호스트에 사내 Root CA를 등록합니다. CA 파일과 등록 명령은 [Ubuntu 서버·클라이언트 CA 등록](../../shared/docs/certificates/apply.md#ubuntu-서버클라이언트)에 있습니다. 관리 호스트는 [관리 호스트 sudo](../../shared/docs/infrastructure/access.md#관리-호스트-sudo), 노드는 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--script`로 실행하고 CA 파일은 같은 명령의 `--copy`로 노드에 보냅니다. 등록 뒤 위 [조회]를 그 호스트에서 다시 실행해 `200` 또는 `401`을 확인합니다.

`curl`은 성공하고 `crictl pull`만 `x509` 오류가 나면 containerd 쪽을 확인합니다.

[조회] 그 노드의 containerd에 이 저장소 전용 설정(별도 endpoint나 CA)이 있는지 확인합니다. 노드에서 실행합니다.

```bash
sudo -n ls /etc/containerd/certs.d/store.etch.samsungds.net
```

`No such file or directory`면 전용 설정이 없고 시스템 신뢰 목록을 쓰는 것입니다(이때 마지막 줄은 `노드 명령 실패: <노드>`입니다). 폴더가 있으면 그 안 `hosts.toml`의 `server`와 CA 지정이 이 저장소와 맞는지 확인합니다.

[승인] CA를 새로 등록한 노드에서 containerd가 등록 전의 신뢰 목록을 쓰고 있으면 containerd를 다시 시작합니다. 대상 노드와 영향을 보여 주고 승인받은 뒤 한 번에 한 대씩 그 노드에서 실행합니다. 블록은 `--script`로 전달합니다.

```bash
sudo -n systemctl restart containerd
sudo -n systemctl is-active containerd
sudo -n crictl pull store.etch.samsungds.net/test/busybox:1.37.0
```

성공: `active`가 출력되고 pull이 `Image is up to date for` 줄로 끝납니다. 시험 이미지가 아직 없으면 [수동 push·pull 시험](#수동-pushpull-시험)의 push를 먼저 실행합니다.

[조회] 관리 호스트에서 그 노드가 `Ready`인지 확인한 뒤 다음 노드로 갑니다.

```bash
kubectl --context "<context>" get node <노드>
```

## 수동 push·pull 시험

`make airflow-image`·`make portal-image` 없이 저장소 자체를 시험할 때 씁니다. 로그인에는 push 계정 파일의 계정을 사용하며, 이미지 도구(`deploy/shared/scripts/image_registry.py`)와 같이 비밀번호를 파일에서 표준 입력으로만 전달합니다.

[변경] 관리 호스트에서 로그인하고 시험 이미지를 올립니다. push 계정 파일을 따로 쓰면 첫 줄의 `deploy/registry/env/push-initial.env` 두 곳을 그 경로(`REGISTRY_PUSH_ENV`와 같은 값)로 바꿉니다.

```bash
sed -n 's/^REGISTRY_PASSWORD=//p' deploy/registry/env/push-initial.env | sudo -n nerdctl login --username "$(sed -n 's/^REGISTRY_USER=//p' deploy/registry/env/push-initial.env)" --password-stdin store.etch.samsungds.net
sudo -n nerdctl pull repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0
sudo -n nerdctl tag repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0 store.etch.samsungds.net/test/busybox:1.37.0
sudo -n nerdctl push store.etch.samsungds.net/test/busybox:1.37.0
```

성공: `Login Succeeded`가 출력되고 네 명령이 모두 오류 없이 끝납니다. `nerdctl`이 없으면 [이미지 빌드 도구](../../README.md#이미지-빌드-도구)를 먼저 준비합니다.

[조회] 올라간 tag를 확인합니다.

```bash
curl -sS https://store.etch.samsungds.net/v2/test/busybox/tags/list
```

성공: 출력의 `tags`에 `1.37.0`이 있습니다.

[변경] 이미지를 받을 노드마다 그 노드에서 실행합니다.

```bash
sudo -n crictl pull store.etch.samsungds.net/test/busybox:1.37.0
```

성공: 관리 호스트의 push와 모든 대상 노드의 pull이 끝납니다. pull은 `Image is up to date for` 줄로 끝납니다. 시험 태그를 삭제하려면 [이미지 정리](#이미지-삭제와-용량-정리)의 [승인] 절차를 따릅니다.
실패: `x509` 오류는 인증서 SAN과 [CA 신뢰](#노드와-관리-호스트의-ca-신뢰), push 중 `401`은 로그인에 쓴 계정 파일과 Secret `registry-htpasswd`의 계정, timeout은 [가이드 C](../README.md#c-배포-후-확인)의 읽기 제한 조회와 VIP 경로, 이름을 찾지 못한다는 오류는 [DNS](../../shared/docs/infrastructure/access.md#dns) 등록을 확인합니다.

## 이미지 push 규칙

- 이미지 이름은 `store.etch.samsungds.net/<앱>:<고유 tag>`입니다. 같은 tag를 다시 push하지 않습니다.
- 이미지에 env·인증서·개인키·ODBC 설정 같은 비밀값을 넣지 않습니다. 노드는 익명으로 이미지를 내려받을 수 있습니다.
- 앱 이미지는 `make airflow-image`, `make portal-image`가 빌드해 push합니다. tag는 소스 내용으로 정해지고 이미 있는 tag는 건너뜁니다([Airflow 이미지 준비](../../airflow/docs/02-artifacts.md#2-이미지-준비), [Portal 가이드](../../portal/README.md)).

## 이미지 삭제와 용량 정리

Zot은 참조가 없는 blob을 24시간 주기로 정리합니다. 더 이상 쓰지 않는 tag는 운영 중인 앱의 tag가 아님을 확인한 뒤 삭제합니다.

[조회] 사용 중인 이미지:

```bash
kubectl --context "<context>" get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' | grep -F 'store.etch.samsungds.net/' | sort -u
```

[승인] 삭제는 되돌릴 수 없습니다. 위 조회 결과에 대상 태그가 없음을 확인하고, 대상 태그를 보여 주고 승인받은 뒤 실행합니다. 실행 위치는 `skopeo`가 설치된 관리 호스트입니다(`command -v skopeo`로 확인하고, 없으면 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절로 준비).
`<push 인증 파일>`은 push 계정으로 이 저장소에 로그인해 생긴 Docker 형식 인증 파일의 경로입니다. [수동 push·pull 시험](#수동-pushpull-시험)의 `nerdctl login`은 nerdctl을 실행한 계정의 홈 아래 `.docker/config.json`에 인증을 저장합니다. `sudo -n`으로 로그인했으면 root 계정의 파일이므로 삭제 명령도 `sudo -n`을 붙여 실행합니다. 아래 예의 `test/busybox:1.37.0` 자리에 대상 이미지와 tag를 넣습니다.

```bash
skopeo delete --authfile "<push 인증 파일>" docker://store.etch.samsungds.net/test/busybox:1.37.0
```

[조회] 삭제한 tag가 목록에서 사라졌는지 확인합니다.

```bash
curl -sS https://store.etch.samsungds.net/v2/test/busybox/tags/list
```

성공: `tags`에 삭제한 tag가 없습니다.

[조회] 저장 용량은 registry Worker에서 확인합니다.

```bash
sudo -n du -sh /appdata/registry
```

## push 계정 교체

새 계정은 저장소 밖 계정 파일(`REGISTRY_USER`, `REGISTRY_PASSWORD` 두 키)로 전달합니다. 저장소의 `push-initial.env`는 고치지 않습니다. 요청에 계정 파일 경로가 있으면 그 파일을 그대로 씁니다.

[변경] 계정 파일이 없으면 저장소 밖에 만듭니다. 위치는 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 앱 설정 폴더를 씁니다. `<새 계정 이름>`은 요청받은 이름이며 영문·숫자·`.`·`_`·`-`만 쓸 수 있고, 이름을 받지 않았으면 현재 계정 파일의 `REGISTRY_USER` 값을 그대로 씁니다. 비밀번호는 새로 생성해 파일에만 쓰고 화면에 출력하지 않습니다.

```bash
install -d -m 0700 "<계정 파일을 둘 폴더>"
(umask 077; printf 'REGISTRY_USER=%s\nREGISTRY_PASSWORD=%s\n' "<새 계정 이름>" "$(openssl rand -hex 32)" > "<새 계정 파일 절대 경로>")
python3 -c 'import sys; sys.path.insert(0, "deploy/shared/scripts"); import image_registry; print("계정:", image_registry.read_account(sys.argv[1])[0])' "<새 계정 파일 절대 경로>"
```

성공: `계정: <새 계정 이름>`.

[승인] 교체하면 이전 계정으로는 push할 수 없고 registry가 한 번 다시 시작합니다. 이미지 데이터는 그대로입니다. 새 계정 이름과 영향을 보여 주고 승인받은 뒤 실행합니다. 이 명령이 배포 기록도 함께 갱신하므로 `make deploy-record`를 따로 실행하지 않습니다.

```bash
make registry-account-rotate KUBE_CONTEXT="<context>" REGISTRY_PUSH_ENV=<새 계정 파일 절대 경로>
```

성공: `push 계정 교체 완료: registry/registry-htpasswd (계정 <이름>)`.

[조회] 교체 뒤 서비스가 돌아왔는지 확인합니다.

```bash
make registry-smoke KUBE_CONTEXT="<context>"
```

성공: `smoke 통과: registry`.

이후 `make airflow-image`·`make portal-image`·`make ops-deploy`에는 같은 `REGISTRY_PUSH_ENV=<새 계정 파일 절대 경로>`를 붙여야 push가 됩니다. [변경] 그 경로를 [운영 위치](../../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다. 비밀번호는 기록하지 않습니다.

## 저장 폴더 직접 준비

`registry-up`이 PV를 처음 만들 때 `PREPARE_IMAGE` Job으로 저장 폴더를 UID·GID 1000, 0750으로 만듭니다. 기존 폴더와 내용은 바꾸지 않습니다.
아래 명령은 `NODE_NAME` Worker에서 실행합니다.

[조회] 폴더의 소유자·권한과 내용을 확인합니다.

```bash
sudo -n ls -ld /appdata/registry
sudo -n ls -A /appdata/registry
```

성공: 폴더가 있으면 `drwxr-x--- ... 1000 1000 ... /appdata/registry`. 폴더가 없다는 출력은 최초 설치 전의 정상 상태이며 `registry-up`이 만듭니다.

[변경] 폴더를 직접 준비해야 할 때만, 폴더가 없는 경우에 실행합니다. 기존 폴더가 있으면 내용과 소유자를 덮어쓰지 않도록 실행하지 않습니다.

```bash
sudo -n install -d -o 1000 -g 1000 -m 0750 /appdata/registry
sudo -n ls -ld /appdata/registry
```

성공: `drwxr-x--- ... 1000 1000 ... /appdata/registry`.

데이터를 다른 Worker로 옮기는 것은 서비스를 멈추고 폴더를 복사한 뒤 새 PV/PVC로 전환하는 데이터 경로 이전입니다. [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)에 해당하며 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)의 순서를 따릅니다.

## registry 주소로 전환

[승인] 기존 Zot Service와 PV/PVC를 그대로 두고 공개 주소를 `registry.etch.samsungds.net`으로 바꾸는 작업입니다. 이 주소를 쓰는 앱(Airflow·Portal의 이미지 참조, 노드의 pull)과 영향을 보여 주고 승인받은 뒤 진행합니다.

1. [변경] SAN에 `registry.etch.samsungds.net`을 포함한 인증서를 [인증서 발급](../../shared/docs/infrastructure/access.md#인증서-발급) 절의 방법으로 준비해 [공용 TLS 등록](../../README.md#공용-tls-등록)의 명령으로 공용 Traefik에 등록하고, [DNS](../../shared/docs/infrastructure/access.md#dns) 절의 방법으로 새 이름을 APP VIP로 연결합니다. 확인: `공용 TLS 등록 완료: registry.etch.samsungds.net`과 `getent hosts registry.etch.samsungds.net`.
2. 전환 기간에는 두 호스트의 HTTPS 라우트를 같은 Zot Service로 연결합니다. 배포 도구는 `REGISTRY_HOST` 하나만 Ingress에 넣으므로 두 host를 함께 여는 Ingress 정의가 저장소 원본에 있어야 합니다. 원본에 없으면 이 단계에서 멈추고 보고하며, Ingress를 직접 고치거나 `REGISTRY_HOST`만 바꿔 기존 주소를 끊지 않습니다.
3. [변경] 관리 호스트에서 새 주소로 로그인하고, 기존 태그 pull과 시험 이미지 push를 [수동 push·pull 시험](#수동-pushpull-시험)의 명령에 새 주소를 넣어 확인합니다.
4. [변경] 빌드 및 배포 설정의 이미지 참조를 새 주소로 옮기고 각 앱 가이드의 업데이트로 반영합니다. 이전 주소를 사용하는 배포·Job·롤백 설정까지 정리한 뒤 `store` 라우트를 내립니다. 라우트를 내리기 전에 [이미지 삭제와 용량 정리](#이미지-삭제와-용량-정리)의 사용 중인 이미지 조회에 `store.etch.samsungds.net/` 이미지가 남아 있지 않은지 확인합니다.
