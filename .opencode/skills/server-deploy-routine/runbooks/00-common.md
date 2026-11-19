# 공통 배포 런북

모든 앱 런북보다 먼저 읽습니다. 원본 문서: [배포 안내](../../../../deploy/README.md) · [배포 준비와 검증](../../../../deploy/shared/docs/operations/02-deploy.md) · [운영과 문제 해결](../../../../deploy/shared/docs/operations/03-operations.md) · [배포 상태 대조](../../../../deploy/shared/docs/operations/04-drift.md). 런북과 원본이 다르면 원본이 우선이며, 차이를 보고합니다.

## 실행 규칙

1. 실행 위치는 관리 호스트 `khplanew01`의 저장소 루트입니다. 명령 전에 `pwd`가 저장소 루트이고 `Makefile`이 있는지 확인합니다.
2. context는 항상 `kubernetes-admin@kubernetes`를 명령에 직접 씁니다. `kubectl config use-context`를 쓰지 않습니다.
3. 명령마다 새 셸이 열릴 수 있습니다. `export`·`read`로 만든 변수에 의존하지 말고 값을 명령에 직접 씁니다. 코드 블록 하나는 한 번의 명령으로 실행합니다.
4. 런북의 명령만 실행합니다. 런북에 없는 명령이 필요하면 원본 문서 절을 확인하고, 그래도 없으면 멈추고 사용자에게 묻습니다.
5. 한 단계가 실패하면 다음 단계로 가지 않습니다. 실패한 명령·종료 코드·오류 마지막 20줄(비밀값 제외)을 보고합니다.
6. 저장소 파일(코드·manifest·env·스크립트·문서)을 수정하지 않습니다. 예외는 `deploy/shared/docs/infrastructure/`의 운영 기록뿐입니다. Git 갱신(`pull`·`fetch`·`checkout`)과 commit은 사용자가 합니다.

## 단계 표시

| 표시 | 뜻 | agent 행동 |
| --- | --- | --- |
| [조회] | 클러스터·파일을 읽기만 함 | 바로 실행 |
| [검사] | 입력·원본을 검사하고 클러스터를 바꾸지 않음 | 바로 실행. 실패하면 멈춤 |
| [변경] | 클러스터·서버를 바꿈 | 실행할 명령·대상·영향을 보여 주고 사용자 승인 후 실행 |
| [사람] | sudo·브라우저·비밀번호·DNS·인증서 발급 등 agent가 할 수 없는 일 | 사용자에게 할 일을 정확히 알려 주고 완료 답을 받은 뒤 다음 단계로 감 |

## 절대 하지 않는 일

- Secret 값, env 파일 내용, 토큰, 개인키, kubeconfig 내용을 읽거나 출력하지 않습니다. env 검사는 `make env-check`·`*-check`로만 합니다.
- PV·PVC·namespace·DB·Worker 데이터 폴더를 삭제·이동하지 않습니다. `helm uninstall`, `kubectl delete namespace`를 실행하지 않습니다.
- `kubectl apply -k deploy/shared/ingress`, `deploy/keycloak/rendered`·`export`의 정적 YAML 적용, 렌더 결과 파일(`deploy/*/rendered/*.yaml`) 직접 적용, `make server-up`을 실행하지 않습니다.
- `make k8s-env APP=keycloak ...`을 실행하지 않습니다. 기존 Keycloak Secret을 덮어씁니다.
- 검사가 실패했는데 다음 단계로 넘어가지 않습니다. 검사를 통과시키려고 파일을 고치지 않습니다.

## 앱 설치 순서

| 순서 | 앱 | 먼저 필요한 것 |
| --- | --- | --- |
| 1 | 공용 Traefik·TLS (이 문서) | Ready Worker, 인증서 파일 |
| 2 | [Keycloak](keycloak.md) | Traefik, TLS |
| 3 | [MinIO](minio.md), [Registry](registry.md) | Traefik |
| 4 | [Airflow](airflow.md) | Keycloak, TLS, 이미지 |
| 4 | [Monitoring](monitoring.md) | Traefik(HTTPS) |
| 4 | [Headlamp](headlamp.md) | Keycloak, 제어면 API server OIDC |
| 4 | [FTP](ftp.md) | 대상 노드·방화벽 |
| 5 | [Portal](portal.md) | Keycloak, MinIO, 외부 PostgreSQL, 이미지 |

## 모든 작업 공통 시작

1. [조회] checkout 확인
   ```bash
   git status --short
   git branch --show-current
   git log -1 --oneline
   ```
   대상 앱 경로(`deploy/<app>`, `apps/<app>`)에 미커밋 변경이 있으면 멈추고 보고합니다.
2. [조회] 클러스터 접속
   ```bash
   kubectl --context kubernetes-admin@kubernetes get nodes -o wide
   ```
   실패하면 kubeconfig·API server 접속 문제이므로 멈추고 보고합니다.
3. [조회] 남은 서버 작업 확인: [서버 적용 대기 작업](../../../../deploy/shared/docs/infrastructure/pending.md)에서 대상 앱 행을 읽어 보고합니다.
4. [조회] 현재 상태 대조
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   종료 코드 `0` 일치, `1` 불일치(배포 필요 또는 수동 변경), `2` 판정 불가. 결과 해석은 `deploy-drift-check` 스킬을 따릅니다. 예상하지 못한 `DRIFT workload`(수동 변경)가 있으면 덮어쓰기 전에 보고합니다.
5. [검사] 저장소 원본 검사
   ```bash
   make server-check APP=<app> PROFILE=prod
   ```
   종료 코드 `0`이면 통과입니다. 출력 문구는 앱마다 다르지만 `통과`가 포함됩니다.

## 공용 TLS 등록

인증서 파일(`fullchain.crt`, `private.key`)은 [사람]이 `deploy/shared/certs/<사이트>/`에 둡니다. PFX 추출은 비밀번호 입력이 필요하므로 [사람]이 [인증서 추출](../../../../deploy/shared/docs/certificates/extract.md)로 합니다.

[변경] host마다 한 번씩 등록합니다. SAN 인증서 하나를 여러 host가 함께 써도 host마다 반복합니다.

```bash
make ingress-tls-up KUBE_CONTEXT=kubernetes-admin@kubernetes TLS_HOST=<공개 host> TLS_CERT_FILE="$PWD/deploy/shared/certs/<사이트>/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/<사이트>/private.key"
```

성공: `공용 TLS 등록 완료: <host>`. 실패: SAN·체인·만료 문제이므로 멈추고 보고합니다.

## 공용 Traefik 검사·갱신

배치(VIP backend)를 바꾸지 않는 일반 갱신입니다.

1. [검사]
   ```bash
   make ingress-check KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`
2. [변경] 앱 문서가 `ingress-up`을 요구하거나 검사가 공용 TLS 마운트 누락을 알릴 때만 실행합니다.
   ```bash
   make ingress-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   kubectl --context kubernetes-admin@kubernetes -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
   ```
   성공: `공용 Ingress 준비 완료`, Traefik Pod `1/1 Running`.

backend 노드를 추가·변경하는 작업은 [사람]과 함께 [Traefik 셋업](../../../../deploy/shared/docs/ingress/setup.md)·[backend 확장](../../../../deploy/shared/docs/ingress/expand.md)을 따릅니다. `VIP_BACKENDS` 값은 사용자에게 받고 기존 backend를 빼지 않습니다.

## 배포 후 공통 마무리

1. [조회] 대조
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   종료 코드 `0`이면 완료입니다. `UNKNOWN record`이고 manifest가 일치하면 다음 단계를 실행합니다.
2. [변경] 배포 기록: `make <app>-up`으로 배포했으면 자동으로 남으므로 생략합니다. `kubectl apply -k` 등 직접 배포했으면 실행합니다.
   ```bash
   make deploy-record APP=<app> KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
3. [조회] 앱 런북의 `C. 배포 후 확인`을 실행합니다.
4. 운영 기록: 서버에서 확인된 값이 [인프라 정보](../../../../deploy/shared/docs/infrastructure/README.md)와 다르면 해당 원본을 `서버 조회` 상태로 고치고, 완료된 [pending](../../../../deploy/shared/docs/infrastructure/pending.md) 행을 삭제합니다. 남은 서버 작업은 행으로 추가합니다. 날짜·완료 기록·비밀값은 쓰지 않습니다.

## 장애 조회

모두 [조회]입니다. `<namespace>`는 앱 런북의 `한눈에 보기` 표에 있습니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n <namespace> get pods -o wide
kubectl --context kubernetes-admin@kubernetes -n <namespace> get events --sort-by=.lastTimestamp
kubectl --context kubernetes-admin@kubernetes -n <namespace> describe pod <Pod 이름>
kubectl --context kubernetes-admin@kubernetes -n <namespace> logs <Pod 이름> --all-containers --tail=100
```

| 증상 | 먼저 볼 것 |
| --- | --- |
| Pending, PVC Pending | events의 자원·taint·nodeSelector·PV affinity |
| ImagePullBackOff | 이미지 tag·사내 미러·노드의 이미지 접근 |
| CrashLoopBackOff | `logs --previous`, env·DB 연결 |
| 404 / 503 | Ingress host·Traefik 감시 namespace / Pod·Service endpoint |
| TLS 오류 | 공용 TLS 등록 host·SAN·만료 |

증상을 보고만 하고, Pod 삭제·재시작·Secret 수정으로 직접 고치지 않습니다. 재시작이 필요하면 앱 런북의 해당 [변경] 단계를 승인받아 실행합니다.

## 보고 형식

- 대상 앱, context, 배포 commit(`git log -1 --oneline`)
- 실행한 단계 번호와 명령, 결과(성공/실패/생략), 구분([조회]/[검사]/[변경]/[사람])
- 최종 `drift-check` 종료 코드와 요약
- 사람이 해야 할 남은 일, 수정한 운영 기록 파일
