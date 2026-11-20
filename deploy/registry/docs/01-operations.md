# Registry 운영 작업

[Registry 가이드](../README.md)

설치·업데이트 절차는 [Registry 가이드](../README.md)에 있습니다. 이 문서는 그 밖의 운영 작업과 사람이 하는 일의 방법입니다.

- [노드와 관리 호스트의 CA 신뢰](#노드와-관리-호스트의-ca-신뢰)
- [수동 push·pull 시험](#수동-pushpull-시험)
- [이미지 push 규칙](#이미지-push-규칙)
- [이미지 삭제와 용량 정리](#이미지-삭제와-용량-정리)
- [push 계정 교체](#push-계정-교체)
- [저장 폴더 직접 준비](#저장-폴더-직접-준비)
- [registry 주소로 전환](#registry-주소로-전환)

## 노드와 관리 호스트의 CA 신뢰

registry 이미지를 받을 모든 노드와 이미지를 올리는 관리 호스트에서 수행합니다. 각 서버의 시스템 신뢰 설정으로 HTTPS 연결을 확인합니다.

```bash
curl -sS -o /dev/null -D - https://store.etch.samsungds.net/v2/
```

성공: 응답 코드가 `200`이거나 `401`이면서 `WWW-Authenticate`에 `realm="registry"`가 보입니다.
신뢰 오류가 나면 [Ubuntu 서버·클라이언트 CA 등록](../../shared/docs/certificates/apply.md#ubuntu-서버클라이언트) 절차를 따릅니다. `curl`은 성공하고 `crictl`만 신뢰 오류가 나면 containerd의 해당 호스트 설정에 별도 endpoint나 CA가 지정돼 있는지 확인합니다. CA를 새로 등록한 노드에서 containerd가 이전 신뢰 설정을 사용하면 영향을 확인하고 containerd를 재시작합니다.

## 수동 push·pull 시험

`make airflow-image`·`make portal-image` 없이 저장소 자체를 시험할 때 씁니다. 로그인에는 push 계정 파일의 계정을 사용합니다.

관리 호스트:

```bash
sudo nerdctl login store.etch.samsungds.net
sudo nerdctl pull repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0
sudo nerdctl tag repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0 \
  store.etch.samsungds.net/test/busybox:1.37.0
sudo nerdctl push store.etch.samsungds.net/test/busybox:1.37.0
```

다른 노드:

```bash
sudo crictl pull store.etch.samsungds.net/test/busybox:1.37.0
```

성공: push와 pull이 모두 끝납니다. 확인 후 [시험 이미지를 삭제](#이미지-삭제와-용량-정리)합니다.
실패: `x509` 오류는 인증서 SAN·CA 신뢰, push 중 `401`은 로그인·Secret, timeout은 [가이드 A-4](../README.md#a-최초-설치)의 읽기 제한과 VIP 경로를 확인합니다.

## 이미지 push 규칙

- 이미지 이름은 `store.etch.samsungds.net/<앱>:<고유 tag>`입니다. 같은 tag를 다시 push하지 않습니다.
- 이미지에 env·인증서·개인키·ODBC 설정 같은 비밀값을 넣지 않습니다. 노드는 익명으로 이미지를 내려받을 수 있습니다.
- 앱 이미지는 `make airflow-image`, `make portal-image`가 빌드해 push합니다. tag는 소스 내용으로 정해지고 이미 있는 tag는 건너뜁니다([Airflow 이미지 준비](../../airflow/docs/02-artifacts.md#2-dag-포함-이미지-준비), [Portal 가이드](../../portal/README.md)).

## 이미지 삭제와 용량 정리

Zot은 참조가 없는 blob을 24시간 주기로 정리합니다. 더 이상 쓰지 않는 tag는 운영 중인 앱의 tag가 아님을 확인한 뒤 삭제합니다.

[조회] 사용 중인 이미지:

```bash
kubectl --context "<context>" get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' | grep -F 'store.etch.samsungds.net/' | sort -u
```

[사람] 삭제는 되돌릴 수 없습니다. 로그인한 계정으로 OCI API를 호출하며 `skopeo`가 있는 host에서는 아래처럼 실행합니다.

```bash
skopeo delete --creds "<push 계정>" docker://store.etch.samsungds.net/test/busybox:1.37.0
```

[사람] 저장 용량은 registry Worker에서 확인합니다.

```bash
sudo du -sh /appdata/registry
```

## push 계정 교체

새 계정은 사람이 정해 계정 파일(`REGISTRY_USER`, `REGISTRY_PASSWORD` 두 키)로 전달합니다. 저장소의 `push-initial.env`를 고치지 않고 저장소 밖 파일을 씁니다.

[승인] 교체하면 이전 계정으로는 push할 수 없고 registry가 한 번 다시 시작합니다. 이미지 데이터는 그대로입니다.

```bash
make registry-account-rotate KUBE_CONTEXT="<context>" REGISTRY_PUSH_ENV=<새 계정 파일 절대 경로>
```

성공: `push 계정 교체 완료: registry/registry-htpasswd (계정 <이름>)`.

[조회] 교체 뒤 서비스가 돌아왔는지 확인합니다.

```bash
make registry-smoke KUBE_CONTEXT="<context>"
```

이후 `make airflow-image`·`make portal-image`·`make ops-deploy`에는 같은 `REGISTRY_PUSH_ENV=<새 계정 파일 절대 경로>`를 붙여야 push가 됩니다. 경로를 [운영 위치](../../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다.

## 저장 폴더 직접 준비

`registry-up`이 PV를 처음 만들 때 `PREPARE_IMAGE` Job으로 저장 폴더를 UID·GID 1000, 0750으로 만듭니다. 기존 폴더와 내용은 바꾸지 않습니다.
폴더를 직접 준비하거나 권한을 확인할 때만 `NODE_NAME` Worker에서 실행합니다.

```bash
sudo install -d -o 1000 -g 1000 -m 0750 /appdata/registry
ls -ld /appdata/registry
```

성공: `drwxr-x--- ... 1000 1000 ... /appdata/registry`. 기존 폴더가 있으면 내용과 소유자를 먼저 확인하고 덮어쓰지 않습니다.
데이터를 다른 Worker로 옮기려면 서비스를 멈추고 폴더를 복사한 뒤 새 PV/PVC로 전환합니다.

## registry 주소로 전환

기존 Zot Service와 PV/PVC를 사용해 주소를 전환합니다.

1. DNS SAN에 `registry.etch.samsungds.net`을 포함한 인증서를 발급받아 공용 Traefik에 등록하고 새 DNS를 APP VIP로 연결합니다.
2. 전환 기간에는 두 호스트의 HTTPS 라우트를 같은 Zot Service로 연결합니다. 관리 호스트에서 새 주소로 로그인하고, 기존 태그 pull과 시험 이미지 push를 확인합니다.
3. 빌드 및 배포 설정의 이미지 참조를 새 주소로 옮깁니다. 이전 주소를 사용하는 배포·Job·롤백 설정까지 정리한 뒤 `store` 라우트를 내립니다.
