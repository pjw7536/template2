# Portal 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/portal/README.md) · [설치](../../../../deploy/portal/docs/01-install.md) · [접근 권한](../../../../deploy/portal/docs/02-access.md) · [운영](../../../../deploy/portal/docs/03-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `tailwind-internal` (Deployment `api`, `web`, `edge-nginx`) |
| 공개 주소 | `https://etch.samsungds.net`, health `/api/v1/health/` |
| 배포 방식 | `make` 배포 타깃 없음. `kubectl apply -k` 후 `make deploy-record`를 직접 실행 |
| 완료 기준 | migration 사후 검사 통과, 세 Deployment rollout 성공, Traefik 감시에 `tailwind-internal` 포함, 사람이 로그인·callback·logout·파일 송수신 확인 |
| 먼저 필요한 것 | Keycloak 설정 완료, MinIO와 Portal 접근 키, 외부 PostgreSQL(`pg_trgm`), 업무 도메인 공용 TLS, API·Web 이미지 |

## 사람이 해야 하는 일

- [사람] API·Web 이미지 빌드·push와 overlay 이미지 태그 반영(저장소 수정). overlay에 `replace-me`·`example.invalid`가 남아 있으면 배포할 수 없음
- [사람] 외부 PostgreSQL DB·계정·`pg_trgm` 준비, 기존 DB 백업
- [사람] `deploy/portal/env/prod/api.env`, `web.env` 실제 값 입력
- [사람] MinIO Portal 접근 키·bucket 정책 등록
- [사람] 기존 환경 갱신 전 worker·Airflow 쓰기 중지, 끝난 뒤 재개
- [사람] Keycloak에서 최초 운영자 `portal-admin` 지정·그룹 가입([접근 권한](../../../../deploy/portal/docs/02-access.md))
- [사람] 브라우저 로그인·callback·logout·파일 업로드·다운로드 확인

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| env | `deploy/portal/env/prod/api.env`(Secret `api-env`), `web.env`(Secret `web-env`, 브라우저에 공개되므로 비밀값 없음) | 저장소 경로 |
| 이미지 | `deploy/portal/k8s/overlays/prod/kustomization.yaml`과 `migrate/kustomization.yaml`의 API 이미지가 같아야 함 | |
| 기존 API replica 수 | 기존 DB 갱신 때 B에서 기록 | 신규 설치는 없음 |

## A. 최초 설치

1. [조회] 이미지 자리표시자 확인
   ```bash
   grep -nE 'replace-me|example\.invalid' deploy/portal/k8s/overlays/prod/kustomization.yaml deploy/portal/k8s/overlays/prod/migrate/kustomization.yaml || echo '이미지 자리표시자 없음'
   ```
   결과가 `이미지 자리표시자 없음`이 아니면 멈추고 [사람]에게 이미지 반영을 요청합니다.
2. [사람] DB·env·MinIO 키·인증서 준비와 Keycloak 설정 완료를 사용자에게 확인합니다.
3. [검사] env 검사
   ```bash
   make env-check APP=portal PROFILE=prod COMPONENT=api
   make env-check APP=portal PROFILE=prod COMPONENT=web
   make env-check APP=portal PROFILE=prod COMPONENT=client
   make server-check APP=portal PROFILE=prod
   ```
   성공: 세 번 `설정 검사 통과`, `서버 원본 검사 통과: portal/prod`.
4. [변경] Keycloak client 등록(승인 필요)
   ```bash
   make keycloak-portal-client-setup KUBE_CONTEXT=kubernetes-admin@kubernetes KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
   kubectl --context kubernetes-admin@kubernetes -n etch-sso logs job/portal-keycloak-client --tail=20
   ```
   성공: 로그 끝에 `portal-members 표준 그룹 준비 완료`.
5. [변경] namespace·Secret 등록(승인 필요)
   ```bash
   kubectl --context kubernetes-admin@kubernetes apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
   make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT=kubernetes-admin@kubernetes
   make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `설정 등록 완료: tailwind-internal / api-env`, `/ web-env`.
6. [변경] 업무 도메인 TLS: `etch.samsungds.net`으로 [공통 TLS 등록](00-common.md#공용-tls-등록)을 합니다. 이미 등록돼 있으면 생략합니다.
7. [조회] 이전 migration Job 확인
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal get job portal-migrate --ignore-not-found
   ```
   최초 설치는 출력이 없어야 합니다. Job이 있으면 멈추고 사람에게 묻습니다.
8. [변경] migration 실행(승인 필요, DB 스키마 변경, 자동 재시도 없음). 원본 문서의 보조 함수를 그대로 읽어 한 번에 실행합니다.
   ```bash
   bash -c 'set -o pipefail; export KUBE_CONTEXT=kubernetes-admin@kubernetes; source <(sed -n "/^portal_wait_job() (/,/^\`\`\`/p" deploy/portal/docs/01-install.md | sed "\$d"); kubectl --context "$KUBE_CONTEXT" apply -k deploy/portal/k8s/overlays/prod/migrate && portal_wait_job portal-migrate'
   ```
   실패하면 앱 적용으로 가지 않고 `kubectl --context kubernetes-admin@kubernetes -n tailwind-internal logs job/portal-migrate --tail=100`을 보고합니다.
9. [변경] 사후 검사(승인 필요, 검사 Job 생성). Job 이름은 겹치지 않게 사용자에게 받습니다(예: `portal-postcheck-1`).
   ```bash
   bash -c 'set -o pipefail; export KUBE_CONTEXT=kubernetes-admin@kubernetes; source <(sed -n "/^portal_wait_job() (/,/^\`\`\`/p" deploy/portal/docs/01-install.md | sed "\$d"); portal_permission_check <사후 검사 Job 이름> post-migration'
   ```
   실패하면 멈춥니다.
10. [변경] 앱 적용(승인 필요)
    ```bash
    kubectl --context kubernetes-admin@kubernetes apply -k deploy/portal/k8s/overlays/prod
    kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/api --timeout=10m
    kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/web --timeout=10m
    kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
    ```
11. [변경] 배포 기록
    ```bash
    make deploy-record APP=portal KUBE_CONTEXT=kubernetes-admin@kubernetes
    ```
12. [변경] 공용 Traefik 연결(승인 필요, Traefik 재기동)
    ```bash
    make ingress-connect APP=portal KUBE_CONTEXT=kubernetes-admin@kubernetes
    kubectl --context kubernetes-admin@kubernetes -n etch-sso rollout status deployment/traefik --timeout=3m
    ```
13. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
14. [사람] 브라우저 확인과 최초 운영자 권한 설정을 요청합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| `api.env` | A-3 → 아래 api 재시작 블록 |
| `web.env` | A-3 → 아래 web 재시작 블록 |
| OIDC client 설정 | A-4 |
| 이미지·manifest(schema 변경 없음) | A-1 → A-3 → A-10 → A-11 → C |
| 이미지(schema 변경 있음, 기존 DB) | 아래 기존 DB migration 순서 |
| DB·Keycloak·MinIO 계정 비밀번호 | 멈추고 사람에게 묻기(실제 서비스 계정 먼저 변경) |

[변경] api.env 반영(승인 필요). Secret만 바꿔서는 Pod에 반영되지 않습니다.

```bash
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout restart deployment/api
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout restart deployment/edge-nginx
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
```

[변경] web.env 반영(승인 필요)

```bash
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout restart deployment/web
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/web --timeout=10m
```

### 기존 DB migration 순서

서비스가 중단되므로 단계마다 승인을 받습니다.

1. [사람] DB 백업·호환성 확인, worker·Airflow 쓰기 중지를 확인받습니다.
2. [조회] 현재 API replica 수를 기록해 보고합니다.
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal get deployment api -o jsonpath='{.spec.replicas}{"\n"}'
   ```
3. [변경] API 중지
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal scale deployment/api --replicas=0
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/api --timeout=5m
   ```
4. [변경] 사전 검사: A-9 명령에서 `post-migration`을 `pre-migration`으로, Job 이름을 새 이름으로 바꿔 실행합니다. 실패하면 멈춥니다.
5. [사람] 이전 `portal-migrate` Job 삭제 여부를 확인받습니다. 완료 상태이고 백업이 확인됐을 때만 사용자가 승인하면 삭제합니다.
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal delete job portal-migrate
   ```
6. A-8 migration → A-9 사후 검사 → A-10 앱 적용
7. [변경] 2단계에서 기록한 replica 수로 복원
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal scale deployment/api --replicas=<기록한 수>
   kubectl --context kubernetes-admin@kubernetes -n tailwind-internal rollout status deployment/api --timeout=10m
   ```
8. A-11 → C → [사람] 쓰기 재개

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal get deployment,pods -o wide
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal get jobs,pvc
kubectl --context kubernetes-admin@kubernetes -n tailwind-internal get service,ingress,endpointslices
kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment traefik -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}'
make drift-check APP=portal KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: 세 Deployment READY, Traefik args에 `tailwind-internal` 포함, drift-check 종료 코드 `0`.

## 멈추고 사람에게 묻는 조건

- overlay 이미지 자리표시자, migrate 이미지와 앱 이미지 불일치
- env-check 실패, Keycloak client Job 실패(issuer 불일치 등)
- `portal-migrate` Job이 이미 있거나 진행 중·실패 상태
- 사전·사후 검사 실패, 같은 이름의 검사 Job이 이미 있음
- 기존 DB인데 백업·쓰기 중지가 확인되지 않음
- PVC Pending, rollout 시간 초과
- DB·PVC·namespace 삭제나 Keycloak 정적 YAML 재적용이 필요해 보이는 경우. 실행하지 않습니다.
