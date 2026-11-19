# 공통 배포 런북

대상 앱 런북과 함께 사용합니다. 사람용 설치 경로는 담당자에게 전달할 때 사용합니다.

## 실행 규칙

1. 실행 위치는 관리 호스트 `khplanew01`의 저장소 루트입니다. 명령 전에 `pwd`가 저장소 루트이고 `Makefile`이 있는지 확인합니다.
2. 사용자가 지정한 context 또는 [운영 위치](../../../../deploy/shared/docs/infrastructure/operations.md)의 기본값을 선택하고 모든 명령의 `<context>`에 같은 실제 값을 넣습니다. `kubectl config use-context`를 쓰지 않습니다.
3. 명령마다 새 셸이 열릴 수 있습니다. `export`·`read`로 만든 변수에 의존하지 말고 값을 명령에 직접 씁니다. 같은 블록의 여러 명령은 첫 실패에서 중단합니다(셸 블록은 `set -e -o pipefail`). 외부 env·chart 경로를 선택했다면 검사·배포·대조의 각 명령에 같은 입력을 명시합니다.
4. 런북의 명령만 실행합니다. 런북에 없는 명령이 필요하면 담당자에게 마지막 성공 단계와 필요한 조치를 전달합니다.
5. drift 결과는 공통 시작 4번의 판정 규칙을 따릅니다. 다른 단계가 실패하면 해당 런북에 명시된 복구 절차에서 멈춥니다. 실패한 명령·종료 코드·오류 마지막 20줄(비밀값 제외)을 보고합니다.
6. 저장소 파일(코드·manifest·env·스크립트·문서)을 수정하지 않습니다. 예외는 `deploy/shared/docs/infrastructure/`의 운영 기록뿐입니다. Git 갱신(`pull`·`fetch`·`checkout`)과 commit은 사용자가 합니다.

배포 기본 env에는 사내 주소와 신규 설치 입력이 들어 있습니다. 별도 운영 입력이 없는 신규 설치는 기본 파일로 시작합니다. 빈 선택 키(예: pull Secret, 알림 수신자)는 해당 기능을 사용하는 경우에만 요청합니다. 재배포는 해당 서비스의 기존 계정·키·파일 경로를 유지합니다.

## 단계 표시

| 표시 | 뜻 | agent 행동 |
| --- | --- | --- |
| [조회] | 클러스터·파일을 읽기만 함 | 바로 실행 |
| [검사] | 입력·원본을 검사하고 클러스터를 바꾸지 않음 | 바로 실행. 실패하면 멈춤 |
| [변경] | 클러스터·서버를 바꿈 | 실행할 명령·대상·영향을 보여 주고 사용자 승인 후 실행 |
| [사람] | sudo·브라우저·비밀번호·DNS·인증서 발급 등 agent가 할 수 없는 일 | 사용자에게 할 일을 정확히 알려 주고 완료 답을 받은 뒤 다음 단계로 감 |

## 절대 하지 않는 일

- Secret 값, env 파일 내용, 토큰, 개인키, kubeconfig 내용을 읽거나 출력하지 않습니다. env는 사전 검사나 앱 소유 검사 타깃을 통해 검증합니다.
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
   대상 배포 경로(`deploy/<app>`)에 미커밋 변경이 있으면 멈추고 보고합니다.
2. [조회] [서버 적용 대기 작업](../../../../deploy/shared/docs/infrastructure/pending.md)에서 대상 앱 행을 확인합니다.
3. [검사] 반입물과 선택한 입력을 확인합니다. 요청한 앱 하나만 지정합니다. 준비 상태만 요청받으면 이 검사 결과를 보고하고 종료합니다.
   ```bash
   make ops-preflight APP=<app> PROFILE=prod KUBE_CONTEXT="<context>"
   ```
   `배포 차단`이면 표시된 파일·키·담당 작업을 전달하고 멈춥니다. 사람이 입력을 준비한 뒤 출력된 명령으로 재검사합니다. `현장 확인 필요`는 해당 앱의 사람 단계에서 확인합니다.
4. [조회] 현재 상태를 대조합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```
   JSON의 `resultCode`와 `apps[].findings`를 읽습니다. 0은 일치, 1은 불일치·경고, 2는 판정 불가입니다. Make 종료 코드만으로 분기하지 않습니다. 유효한 JSON이 없거나 조회에 실패하면 멈춥니다. 기록이 없으면 워크로드와 보존 데이터 유무를 확인하고 설치·갱신이 모호하면 사람에게 묻습니다. 예상 밖 수동 변경은 덮어쓰기 전에 보고합니다.

## 공용 TLS 등록

인증서 파일(`fullchain.crt`, `private.key`)은 [사람]이 `deploy/shared/certs/<사이트>/`에 둡니다. PFX 추출은 비밀번호 입력이 필요하므로 [사람]이 인증서 추출 (사람용 `deploy/shared/docs/certificates/extract.md`)로 합니다.

[변경] host마다 한 번씩 등록합니다. SAN 인증서 하나를 여러 host가 함께 써도 host마다 반복합니다.

```bash
make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=<공개 host> TLS_CERT_FILE="$PWD/deploy/shared/certs/<사이트>/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/<사이트>/private.key"
```

성공: `공용 TLS 등록 완료: <host>`. 실패: SAN·체인·만료 문제이므로 멈추고 보고합니다.

## 공용 Traefik 검사·갱신

배치(VIP backend)를 바꾸지 않는 일반 갱신입니다.

1. [검사]
   ```bash
   make ingress-check KUBE_CONTEXT="<context>"
   ```
   성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`
2. [변경] 대상 런북이 `ingress-up`을 요구하거나 검사가 공용 TLS 마운트 누락을 알릴 때만 실행합니다.
   ```bash
   make ingress-up KUBE_CONTEXT="<context>"
   kubectl --context "<context>" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
   ```
   성공: `공용 Ingress 준비 완료`, Traefik Pod `1/1 Running`.

backend 노드 추가·변경은 [사람]에게 맡기고 Traefik 셋업 (사람용 `deploy/shared/docs/ingress/setup.md`)·backend 확장 (사람용 `deploy/shared/docs/ingress/expand.md`) 절차를 전달합니다. `VIP_BACKENDS` 값은 사용자에게 받고 기존 backend를 빼지 않습니다.

## 배포 후 공통 마무리

1. 앱 런북 C의 rollout·서비스 확인을 한 번 실행합니다. 직접 적용한 배포는 완료된 단계와 입력 경로를 확인하고 승인 후 `make deploy-record APP=<app> KUBE_CONTEXT="<context>"`로 기록합니다. 앱 런북이나 배포 타깃에서 이미 기록했으면 생략합니다. 상태 점검 중 발견한 차이를 없애기 위해 기록을 바꾸지 않습니다.
2. [조회] 공통 시작 4번과 같은 명령·입력으로 대조합니다. 전체 비교의 `resultCode`가 0이고 C의 성공 조건이 충족돼야 합니다. 기능 확인을 사람이 해야 하면 그 결과까지 따로 보고합니다.
3. 운영 기록: 서버에서 확인된 값이 [인프라 정보](../../../../deploy/shared/docs/infrastructure/README.md)와 다르면 해당 원본을 `서버 조회` 상태로 고치고, 완료된 [pending](../../../../deploy/shared/docs/infrastructure/pending.md) 행을 삭제합니다. 남은 서버 작업은 행으로 추가합니다. 날짜·완료 기록·비밀값은 쓰지 않습니다.

## 장애 조회

모두 [조회]입니다. `<namespace>`는 앱 런북의 `한눈에 보기` 표에 있습니다.

```bash
kubectl --context "<context>" -n <namespace> get pods -o wide
kubectl --context "<context>" -n <namespace> get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n <namespace> describe pod <Pod 이름>
kubectl --context "<context>" -n <namespace> logs <Pod 이름> --all-containers --tail=100
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
- 최종 JSON 판정과 근거, 마지막 성공 단계·현재 서비스 상태·담당자와 재개 지점
- 사람이 해야 할 남은 일, 수정한 운영 기록 파일
