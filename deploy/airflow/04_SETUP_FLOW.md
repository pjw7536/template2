# 04. Airflow 단계별 검사·배포·접속

[시작 안내](README.md) · 이전: [차트·이미지](03_ARTIFACTS.md) · 다음: [운영](05_OPERATIONS.md)

서버·env·차트·이미지·ODBC 준비가 끝난 뒤 사용합니다. 명령은 저장소 루트의 Bash에서 실행합니다.
아래 기본 흐름은 `deploy/airflow/env/k8s.env`, namespace `airflow` 기준입니다.
namespace를 바꿨다면 kubectl의 `-n airflow`도 바꿉니다.
다른 env는 Python에 `--env`, Makefile에 `AIRFLOW_ENV`로 같은 파일을 전달합니다.

## 실행 순서와 영향

| 단계 | 실행 목적 | 변경 대상 | 완료 기준 |
| --- | --- | --- | --- |
| 0 | 대상 context 선택 | 셸 변수 | 의도한 클러스터의 노드 조회 |
| 1 | 설정·chart 검사 | 없음 | 정적 검사 통과 |
| 2 | manifest 검토 | 로컬 rendered 파일 | 노드·이미지·디스크·Ingress가 의도와 일치 |
| 3 | 클러스터 사전 검사 | 없음 | 버전·노드·기존 비밀값 검사 통과, Ingress 사용 시 Traefik·TLS 확인 |
| 4 | 실제 배포 | Airflow·DB·스토리지·Secret, 필요한 공용 라우팅 | Helm hook·Pod rollout 완료 |
| 5 | 접속·업무 연동 확인 | 시험 작업과 선택한 DAG 상태 | 로그인·DAG 로딩·Portal 호출 확인 |

최초 설치는 순서대로 진행합니다. 재배포는 [백업·업데이트](05_OPERATIONS.md)를 먼저 확인합니다.
검사 실패 시 다음 단계로 넘어가지 말고 원인을 고친 뒤 해당 검사를 다시 실행합니다.

## 0. 대상 context 선택

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
```

현재 기본 context에 의존하지 않도록 이후 명령에도 context를 명시합니다.
새 터미널을 열면 이 단계를 다시 수행합니다.

## 1. 설정과 차트 검사

```bash
make server-check APP=airflow PROFILE=prod
python3 deploy/airflow/scripts/manage.py check \
  --env deploy/airflow/env/k8s.env --pause-new-dags
```

첫 명령은 저장소 env 구조와 고정 chart의 렌더를 검사합니다.
두 번째는 실제 입력으로 예시값·비밀값 길이·URL·Fernet 키 형식까지 검사합니다.
둘 다 클러스터에 연결하지 않으며 차트를 자동 다운로드하지 않습니다.
완료 기준: 각각 원본 검사 통과 메시지가 나와야 합니다.

## 2. 배포 내용 미리 보기

```bash
python3 deploy/airflow/scripts/manage.py render \
  --env deploy/airflow/env/k8s.env --pause-new-dags \
  --output deploy/airflow/rendered
```

| 출력 | 검토할 내용 |
| --- | --- |
| `storage.json` | Worker hostname, DB·로그 경로와 용량, Retain 정책 |
| `postgres.json` | 내부 DB 이미지·권한·Service, external 모드에서는 빈 리소스 목록 |
| `values.json` | 이미지 태그·노드·ODBC·URL·신규 DAG 일시정지 설정 |
| `airflow.yaml` | Airflow workload·Ingress·migration 및 관리자 Job |

Secret 값은 출력에 포함하지 않습니다. **`airflow.yaml`을 직접 kubectl apply하지 않습니다.**
실제 배포는 Helm hook을 통해 DB migration과 관리자 생성 순서를 지켜야 합니다.
`--pause-new-dags`는 기본 make 배포와 동일한 신규 DAG 정책으로 검토하기 위한 옵션입니다.

## 3. 클러스터 사전 검사

```bash
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

클러스터 버전, 대상 노드 Ready·cordon 상태, 기존 DB 비밀번호와 Fernet 키를 조회합니다.
Ingress를 사용하면 `etch-sso/traefik`과 TLS 인증서 도메인·만료도 검사합니다.
검사 통과는 실제 디스크 권한·이미지 pull·외부 DB 접속·Portal 연동 성공을 보장하지 않습니다.

운영 URL은 `https://etch.samsungds.net/airflow`, `INGRESS_TLS_SECRET=airflow-tls`입니다.
Airflow namespace에 TLS Secret이 아직 없다면 기존 `headlamp/headlamp-tls`를 원본으로 지정합니다.
원본이 없다면 먼저 [Headlamp TLS 등록](../headlamp/03_TLS.md)을 완료합니다.
Airflow 공개 도메인이 인증서에 포함되어 있어야 하며 실행 호스트에는 OpenSSL이 필요합니다.

```bash
AIRFLOW_TLS_SOURCE_REF=headlamp/headlamp-tls
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_TLS_SOURCE="$AIRFLOW_TLS_SOURCE_REF"
```

이 검사는 인증서를 복사하지 않습니다. 4단계 배포 시 동일한 `AIRFLOW_TLS_SOURCE`를 전달합니다.
이미 대상 TLS Secret이 있으면 그 인증서를 검사하고 유지합니다. source 지정은 기존 인증서를 갱신하는 명령이 아닙니다.
`INGRESS_ENABLED=false`이면 TLS source가 필요 없습니다.

## 4. 실제 배포

```bash
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

3단계에서 TLS source를 지정했다면 위 명령 대신 다음 명령을 사용합니다.

```bash
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_TLS_SOURCE="$AIRFLOW_TLS_SOURCE_REF"
```

Ingress 사용 시 namespace·TLS·공용 Traefik의 감시 권한을 준비한 뒤 Airflow를 배포합니다.
Keycloak과 Keycloak DB는 재배포하지 않습니다. 공용 Traefik의 설정 변경과 rollout은 발생할 수 있습니다.
이후 namespace → Secret → local PV/PVC → 내부 PostgreSQL 준비 → Helm migration·관리자 생성 → Airflow rollout 순서로 진행합니다.
외부 DB 모드에서는 내부 PostgreSQL 적용과 대기를 생략합니다.

기존 DB/PVC는 삭제하지 않습니다. 기존 Secret과 DB 비밀번호·Fernet 키가 다르면 중단합니다.
기존 PVC가 있는데 DB Secret만 없다면 실제 DB 비밀번호로 Secret을 먼저 복원해야 합니다.
관리자 계정은 없을 때만 생성하며, env의 관리자 비밀번호를 바꾸어도 기존 계정의 비밀번호·역할은 바뀌지 않습니다.
다른 runtime Secret 변경은 배포 마지막 Pod 재시작으로 반영합니다.

**신규 DAG는 일시정지로 생성하고 기존 DB의 DAG 활성 상태는 유지합니다.**
기존 scheduler가 있다면 전환 전에 작업을 정리하고 중지해야 합니다.
완료 기준: migration·관리자 hook과 scheduler·webserver·triggerer rollout이 끝나야 합니다.

## 5. 접속과 연동 확인

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc -o wide
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get ingress
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow port-forward svc/airflow-webserver 8080:8080
```

port-forward는 터미널을 점유하며 Ctrl+C로 종료합니다. 같은 컴퓨터의 브라우저에서
`http://localhost:8080/airflow`에 접속합니다. 원격 서버에서 실행했다면 PC에서 별도 SSH 터널을 연결합니다.

```bash
read -r -p 'port-forward 실행 서버 user@host: ' AIRFLOW_SSH_TARGET
ssh -N -L 8080:127.0.0.1:8080 "$AIRFLOW_SSH_TARGET"
```

HTTPS를 사용하면 `AIRFLOW_WEBSERVER_BASE_URL`의 주소로도 접속합니다.
DNS는 실제 Ingress 진입 주소를 가리켜야 하며 `/airflow` 경로를 rewrite하지 않습니다.

1. 최초 관리자 또는 기존 계정으로 로그인합니다.
2. DAG가 보이고 import 오류가 없는지 확인합니다.
3. 기존 Connection·Variable 복호화와 ODBC 설정을 확인합니다.
4. Airflow → Portal API 주소와 trigger token을 양쪽에서 맞추고 시험 작업으로 확인합니다.
5. Portal → Airflow 호출도 쓴다면 아래 Portal 소유 설정을 확인합니다.
6. 기존 scheduler의 중복 실행이 없는지 확인한 뒤 필요한 DAG만 활성화합니다.

| Portal 설정 | 의미 |
| --- | --- |
| `AIRFLOW_BASE_URL` | 내부 호출 주소. 기본 namespace 예: `http://airflow-webserver.airflow.svc.cluster.local:8080/airflow` |
| `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` | 실제 Airflow 계정과 일치 |
| `AIRFLOW_PUBLIC_BASE_URL` | 브라우저에서 접근하는 Airflow 공개 URL |

위 변수는 Portal 설정이며 Airflow k8s.env에 추가하지 않습니다. namespace를 바꾸면 내부 DNS도 수정합니다.
Pod Ready와 실제 업무 성공은 별도 확인입니다. 실패 시 [문제 해결](05_OPERATIONS.md#4-실패-단계-확인)을 사용합니다.

## 6. 고급: 직접 deploy와 Helm override

기본 운영 흐름은 위 Makefile 명령입니다. 별도 Ingress controller나 환경별 Helm override가 필요한 경우에만
직접 명령을 사용합니다. 이 경로는 공용 Traefik 연결이나 TLS 복사를 하지 않으므로
controller·라우팅·TLS Secret·imagePullSecret·ODBC Secret을 먼저 준비해야 합니다.

```bash
python3 deploy/airflow/scripts/manage.py deploy \
  --env deploy/airflow/env/k8s.env --context "$AIRFLOW_KUBE_CONTEXT" \
  --pause-new-dags
```

`--pause-new-dags`를 생략하면 저장소 `helm/values.yaml` 기본값에 따라 **신규 DAG가 활성 상태로 생성**됩니다.
기존 DAG의 일시정지 상태는 어느 경로에서도 유지합니다.

환경별 비밀값 없는 override가 필요하면 `check`, `render`, `deploy` 모두 동일한
`--values /절대경로/values.yaml`을 전달합니다. Makefile의 airflow-check/up에는 이 override 전달 기능이 없습니다.
override는 생성 values 뒤에 적용되므로 노드·DAG 정책까지 덮어쓸 수 있습니다. 렌더 결과를 반드시 확인합니다.

자원 기본값은 `helm/values.yaml`과 `k8s/postgres/stack.json`이 원본입니다.
parallelism=32, DAG별 task=16·run=16, 웹서버 worker=4이며 초기화 Job은 default_pool slots를 -1로 설정합니다.
CPU·메모리 제한은 실제 작업량과 서버 사양에 맞춰 조정합니다.
