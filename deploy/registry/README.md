# Registry 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

사내 이미지 저장소(Zot)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 사내에서 빌드한 이미지(Airflow·Portal)를 보관하고 각 노드가 내려받게 하는 OCI registry |
| namespace | `registry` (Deployment `registry`, Secret `registry-htpasswd`) |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/registry`(없으면 `registry-up`이 UID·GID 1000으로 생성) |
| 주소 | `https://store.etch.samsungds.net`. DNS → APP VIP 443 → 공용 Traefik hostPort 443 → Zot |
| 배포 명령 | `make ops-deploy APP=registry` = `registry-check` → `registry-up` → `registry-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, PVC `Bound`, `/v2/`가 200 또는 401 |
| 먼저 필요한 것 | 공용 Traefik, `store.etch.samsungds.net`의 공용 TLS |

## 구성

- push: 관리 호스트의 `make airflow-image`·`make portal-image`가 htpasswd 계정으로 로그인한 뒤 올립니다.
- pull: 각 노드의 containerd가 익명으로 내려받습니다. 외부 공개 이미지는 계속 사내 미러에서 받습니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. `registry` namespace 감시는 `registry-up`이 추가합니다.
- 저장: 지정 Worker 한 대의 local PV(`Retain`)입니다. Pod가 멈추면 이미지를 아직 받지 않은 노드에서 새 Pod가 시작되지 않고, 이미 받은 이미지로 실행 중인 Pod는 영향이 없습니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| `store.etch.samsungds.net`이 SAN에 있는 인증서 파일 배치 | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt deploy/shared/certs/etch.samsungds.net/private.key` |
| DNS `store.etch.samsungds.net` → APP VIP 등록 | `getent hosts store.etch.samsungds.net` |
| 관리 호스트가 저장소 인증서를 신뢰(시스템 CA 등록) | `curl -sS -o /dev/null -w '%{http_code}\n' https://store.etch.samsungds.net/v2/`가 200 또는 401 |
| 모든 노드의 containerd가 저장소 인증서를 신뢰([방법](docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)) | 다른 노드에서 이 저장소의 이미지를 쓰는 Pod가 `ImagePullBackOff` 없이 뜨는지로 확인 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `REGISTRY_ENV` | Registry env 경로 | `deploy/registry/env/k8s.env` |
| `REGISTRY_PUSH_ENV` | push 계정 파일. Secret `registry-htpasswd`가 없을 때만 사용하고 기존 Secret은 바꾸지 않음 | `deploy/registry/env/push-initial.env` |

env 파일의 키입니다.

| 키 | 의미 |
| --- | --- |
| `NODE_NAME` | registry를 실행할 Worker의 `kubernetes.io/hostname` 값 |
| `REGISTRY_IMAGE` | 사내 ghcr.io 미러의 Zot 고정 tag 이미지 |
| `PREPARE_IMAGE` | 저장 폴더 준비 Job이 쓰는 셸 포함 이미지(Docker Hub 사내 미러의 busybox 고정 tag) |
| `IMAGE_PULL_SECRET` | Zot 이미지를 받을 때 필요한 pull Secret 이름. 인증이 없으면 비움 |
| `REGISTRY_HOST` | 노드와 관리 호스트가 접근할 DNS 이름. scheme·포트 없이 입력 |
| `DATA_HOST_PATH` | Worker의 이미지 저장 폴더 |
| `STORAGE_SIZE` | PV/PVC 용량. 디스크 여유에 맞춰 지정 |

## A. 최초 설치

1. [검사] 인증서 파일 확인: 위 표의 `ls` 명령.
2. [변경] 공용 TLS 등록: `store.etch.samsungds.net`을 사이트 폴더 `etch.samsungds.net`으로 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
3. [변경] 배포. namespace·push 계정 Secret·저장 폴더·PV·Zot·Ingress를 한 번에 준비합니다.
   ```bash
   make ops-deploy APP=registry KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   push 계정 Secret은 bcrypt htpasswd로 만듭니다. `htpasswd`(apache2-utils)가 없으면 Python `crypt`를 쓰고, 둘 다 쓸 수 없으면 오류로 멈춥니다.
4. [조회] Traefik 업로드 시간 설정 반영 여부. 큰 레이어 업로드를 위해 HTTPS entrypoint의 읽기 제한이 600초여야 합니다.
   ```bash
   kubectl --context "<context>" -n etch-sso get deployment traefik -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}' | grep -Fc -- '--entrypoints.websecure.transport.respondingTimeouts.readTimeout=600s'
   ```
   결과가 `1`이면 다음 단계로 갑니다. `0`이면 [공용 Traefik 갱신](../README.md#공용-traefik-검사갱신)의 `ingress-check` → `ingress-up`을 실행하고 다시 조회합니다(Traefik 재기동).
5. [조회] [C. 배포 후 확인](#c-배포-후-확인)
6. [변경] 운영 기록: 확인된 결과로 [pending](../shared/docs/infrastructure/pending.md)의 registry 관련 행을 정리합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지 태그 | [변경] `make ops-deploy APP=registry KUBE_CONTEXT="<context>"`. `registry-up`은 매번 재시작함 |
| 공용 Traefik 설정 변경 | A-4 |
| push 계정 교체 | 사람에게 새 계정 파일을 받은 뒤 [승인] [방법](docs/01-operations.md#push-계정-교체)의 `make registry-account-rotate` |
| 이미지 태그 삭제 | [사람] 되돌릴 수 없음. [방법](docs/01-operations.md#이미지-삭제와-용량-정리) |
| 주소 전환(`registry.etch.samsungds.net`) | 멈추고 사람에게 묻기. [방법](docs/01-operations.md#registry-주소로-전환) |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n registry get pods,pvc,ingress
make registry-smoke KUBE_CONTEXT="<context>"
```

성공: Pod Running, PVC Bound, `smoke 통과: registry`(`/v2/` 200 또는 401).

## 문제 해결과 멈춤 조건

smoke가 `DNS 조회 실패`이면 DNS 등록 전입니다. APP VIP 주소([별칭 표](../shared/docs/infrastructure/aliases.json)의 `VIP-APP`)로 [조회] 서비스 자체를 확인하고 DNS 등록을 요청합니다.

```bash
make registry-smoke KUBE_CONTEXT="<context>" SMOKE_CONNECT=<APP VIP 주소>
```

| 증상 | 원인과 조치 |
| --- | --- |
| smoke `/v2/ 404` | registry Ingress와 Traefik의 `registry` namespace 감시. [변경] `make registry-up KUBE_CONTEXT="<context>"` 재실행 |
| VIP 직접은 통과, DNS는 실패 | [사람] DNS 등록 |
| smoke `연결 실패` | APP VIP 443 전달 또는 Traefik hostPort 443. Traefik Pod 상태를 조회하고 VIP 전달 확인을 요청 |
| smoke `TLS 검증 실패` | 공용 TLS 등록·SAN·체인. A-2 재실행 후에도 같으면 인증서 재발급 요청 |
| Pod 재시작 반복 | 저장 폴더 권한(1000:1000). [조회] `kubectl --context "<context>" -n registry logs deployment/registry --tail=100` |
| push 중 `x509` / `401` / timeout | CA 신뢰 / 로그인·Secret / A-4의 읽기 제한 |

멈추고 사람에게 묻는 조건입니다.

- `registry-check` 실패 중 노드 Ready·taint, 기존 PV 경로·노드 불일치, PV Released
- bcrypt htpasswd를 만들 수 없다는 오류
- PVC Pending, 이미지 pull 실패
- 기존 `/appdata/registry`에 내용이 있는데 PV가 없음, 다른 Worker로 옮겨야 함
- containerd 설정 변경·재시작이 필요한 경우(노드 영향, 사람만)

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [운영 작업](docs/01-operations.md) | 노드와 관리 호스트의 CA 신뢰, 수동 push·pull 시험, 이미지 push 규칙, 삭제와 용량 정리, push 계정 교체, 저장 폴더 직접 준비, 주소 전환 |
