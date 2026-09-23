# 사내 Keycloak 스택 배포

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

## 서버에 복사한 뒤 넣을 파일

프로젝트 내부에 운영 입력을 둘 때는 아래 폴더를 사용합니다. 일반 env는 Git에 포함하고 비밀값·인증서는 제외합니다.

```text
deploy/keycloak/env/prod.env                  # 운영 입력
deploy/shared/certs/etch-sso.samsungds.net/    # Keycloak 인증서·개인키
```

[env 입력 안내](env/README.md)와 [공용 인증서 추출·적용 안내](../shared/certs/README.md)를 따릅니다.
`make keycloak-check/up`은 위 공용 인증서 폴더를 기본으로 사용합니다.
인증서 파일 배치 자체는 DB나 클러스터를 변경하지 않습니다.

## Keycloak만 검사하고 배포하기

env·인증서·worker 디스크를 준비한 뒤 저장소 루트에서 실행합니다.
Python 3.10+·kubectl·Bash·OpenSSL이 필요합니다. Airflow 파일·Helm·Docker는 필요하지 않습니다.

```bash
read -r -p '배포할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`keycloak-check`는 입력과 기존 클러스터를 조회하고 적용하지 않습니다.
`keycloak-up`은 없는 runtime/TLS Secret만 생성하고 PostgreSQL·Keycloak·Traefik을 적용합니다.
DB·PVC·기존 Secret을 삭제하지 않습니다. 기존 Secret과 파일이 다르면 배포 전에 중단하므로
기존 값에 맞추거나 의도한 Secret 갱신을 별도로 수행합니다. 기존 PVC만 있고 runtime Secret이
없다면 실제 DB 비밀번호에 맞춰 Secret을 먼저 복원합니다. **빈 DB 재설치는 별도 작업입니다.**

입력 파일을 다른 위치에 둘 때는 `KEYCLOAK_ENV=/절대경로/prod.env`,
`KEYCLOAK_CERTS=/인증서/폴더`를 지정합니다. VIP 첫 배포 시 검사와 배포 양쪽에
`VIP_BACKENDS=10.172.40.117,10.172.40.87`을 지정합니다(현재 인프라에 해당하는 값).
이후 기존 VIP와 다른 앱의 namespace 감시는 유지합니다.
worker 파일 존재·권한·이미지 pull·실제 HTTPS 접속은 서버에서 추가 확인해야 합니다.

사내 OIDC와 claim 등록은 아래 6~7절의 별도 Job을 사용합니다. Airflow는 이후
`make airflow-check` → `make airflow-up`으로 따로 배포합니다.
기존 `make server-up`은 두 앱을 함께 적용하는 호환 명령입니다.

전체 폴더 구성은 [Kubernetes 배포 안내](../README.md)를 참고합니다. 환경설정은 `env/`, 배포 원본은 `k8s/`, 생성 도구는 `scripts/`, 전달 YAML은 `rendered/`에 둡니다.
`k8s/`는 overlay 없이 독립 배포하며, `k8s/server/stack.yaml`에 서버 리소스를 모으고
`k8s/kustomization.yaml`이 이미지와 ConfigMap을 묶습니다.

`k8s/server/`는 기본 기동, `k8s/oidc/`는 사내 로그인 연결,
`k8s/claims/`는 사용자 프로필·속성 매핑을 담당합니다.
파일별 역할과 적용 순서는 [Kubernetes 폴더 안내](k8s/README.md)를 참고합니다.

수동 운영 YAML 전달 방식을 선택한 경우 CP1에 `rendered/internal-keycloak-stack.yaml`과
`rendered/internal-keycloak-claim-mappers.yaml`을 전달합니다. 권장 앱별 배포 도구는 선택 checkout을 사용합니다.
프로필·mapper 관리는 Job으로 통일하며 별도 Python 도구는 사용하지 않습니다.

이 디렉터리는 `khplane01w09`(`10.172.40.87`) worker에 다음 리소스를 배포합니다.

- Keycloak 26.7.1 단일 replica
- PostgreSQL 16 단일 replica
- `/appdata/keycloak-postgres` 기반 50Gi 정적 local PersistentVolume
- worker host port 80/443을 사용하는 Traefik Ingress Controller
- 앱 client가 없는 `etch` realm 초기 설정

`k8s/` 기본 원본의 Traefik은 `etch-sso`만 감시합니다. `make k8s-export`는
`export/`의 운영 설정을 적용해 전달 YAML을 생성합니다. 전달 YAML의 Traefik은
2개 replica, RollingUpdate(`maxSurge: 0`, `maxUnavailable: 1`), `etch-sso,headlamp` 감시,
`ingress: traefik` 노드 선택을 사용합니다. 기존 Headlamp RBAC와 해당 라벨을 가진
배치 가능한 노드 2개가 필요합니다. hostPort 80/443을 사용하므로 두 Pod는 서로 다른 노드에 배치됩니다.
Ingress는 기존 도메인과 `keycloak-tls`
Secret을 유지하며 annotation으로 `websecure` entrypoint와 TLS 사용을 명시합니다. Portal 연결은
[Portal 운영 안내](../portal/k8s/overlays/prod/README.md)의 순서로 권한을 먼저 준비한 뒤
감시 범위를 확장합니다. 전달 YAML을 직접 적용하면 명시되지 않은 Portal 등의 감시가 해제될 수 있습니다.
공유 환경의 재배포는 기존 감시 범위·VIP를 보존하는 `make keycloak-up`을 사용합니다.

현재 구성은 단일 worker와 로컬 디스크에 종속되므로 HA가 아닙니다. worker 또는 디스크
장애에 대비한 PostgreSQL 외부 백업은 별도로 준비해야 합니다.

기존 Keycloak에 Airflow를 연결할 때는 [Airflow 안내](../airflow/README.md)의 `make airflow-up`을 사용합니다.
[서버 기동 안내](../shared/docs/operations/server-start.md)의 `make server-up`은 기존 통합 운용을 위한 호환 경로입니다.
Traefik 소스는 [공용 ingress](../shared/ingress/README.md)에 있으며 현재 Kustomize 진입점이 함께 참조합니다.

## 1. Worker 사전 준비

`/appdata/keycloak-postgres`는 local PersistentVolume을 적용하기 전에 worker에 존재해야
합니다. node 관리자 권한으로 디렉터리와 실제 여유 공간을 확인합니다.

```bash
sudo install -d -m 0700 /appdata/keycloak-postgres
df -h /appdata/keycloak-postgres
sudo ss -lntp | grep -E ':(80|443)[[:space:]]' || true
```

80/443 포트를 다른 프로세스가 사용 중이면 Traefik을 배포하기 전에 충돌을 해소해야
합니다. worker에 직접 접속할 수 없다면 node 관리 담당자가 이 단계만 수행해야 합니다.

## 2. DNS와 TLS 준비

PFX 추출, Fullchain 생성, Secret 등록, Ubuntu·Windows 신뢰 설정은
[HTTPS 인증서와 Secret 운영 가이드](TLS.md)를 따릅니다. Secret은 별도 Pod가 아니라
Kubernetes에 저장하는 데이터이며 `keycloak-tls`는 Traefik이 사용합니다.

Keycloak 공개 DNS는 `etch-sso.samsungds.net`입니다. 기존 Worker 직결과 APP VIP 전환 여부는
[현황](../shared/docs/infrastructure/cluster.md)을 확인합니다. APP VIP 사용 시 직접 HTTPS·로그인 검증 후
DNS를 전환하며 TLS 인증서 SAN에는 공개 DNS가 포함되어야 합니다.

```bash
rg -n 'example.invalid|replace-me' deploy/keycloak/k8s
```

위 명령 결과가 없어야 Keycloak 스택을 운영 주소로 배포할 수 있습니다. DNS 발급 전
테스트가 필요하면 예정된 DNS를 테스트 PC의 hosts 파일에만 임시 등록할 수 있지만,
TLS 인증서의 DNS 이름도 동일해야 합니다.

## 3. Namespace와 Secret 생성

아래 3~4절은 수동 단독 배포 경로입니다. 위의 `make keycloak-up`으로 준비했다면 반복하지 않습니다.
특히 공용 앱·APP VIP 구성에서는 4절의 정적 스택 apply 대신 앱별 도구를 사용합니다.

일반 설정은 `deploy/keycloak/env/prod.env`, 실제 credential은 Git 제외 파일인 `deploy/keycloak/env/prod.secrets.env`에서 관리합니다. 배포 도구가 자동 병합합니다.
`deploy/keycloak/env/prod.env.example`을 참고하며 기존 실제 파일이 있으면 덮어쓰지 않습니다.
환경설정 전체 구조는 [앱별 환경설정](../shared/docs/configuration/environment.md)을 참고합니다.

```dotenv
bootstrap-admin-username=<초기 Keycloak 관리자 계정>
keycloak-public-url=https://etch-sso.samsungds.net
```

비밀번호는 `prod.secrets.env`에만 입력합니다.

```dotenv
postgres-password=<기존 PostgreSQL 비밀번호>
bootstrap-admin-password=<기존 초기 관리자 비밀번호>
```

Keycloak 공개 URL은 `/`로 끝나지 않게 작성합니다. Portal client secret과 주소는
Portal API 설정에서 관리하며 서버 기동에는 필요하지 않습니다.

```bash
# 일반 설정은 Git에 포함됩니다. 비밀값 파일은 기존 서버의 값을 준비합니다.
chmod 600 deploy/keycloak/env/prod.secrets.env
vi deploy/keycloak/env/prod.secrets.env
make env-check APP=keycloak PROFILE=prod COMPONENT=server
kubectl create namespace etch-sso --dry-run=client -o yaml | kubectl apply -f -
make k8s-env APP=keycloak PROFILE=prod COMPONENT=server
kubectl create secret tls keycloak-tls \
  --namespace etch-sso \
  --cert=deploy/shared/certs/etch-sso.samsungds.net/fullchain.crt \
  --key=deploy/shared/certs/etch-sso.samsungds.net/private.key \
  --dry-run=client -o yaml | kubectl apply -f -
```

초기 관리자 credential은 첫 기동에만 관리자 생성에 사용합니다. claim 등록 Job도 같은
Secret 항목으로 로그인하므로 실제 관리자 비밀번호와 일치해야 합니다. 운영 관리자 구성을
확인한 뒤 bootstrap 항목을 제거하려면 Deployment와 Job의 동일 env 참조도 함께 변경합니다.

## 4. Control-plane에서 배포

전체 Portal을 아직 배포하지 않는다면 단일 배포 파일
`deploy/keycloak/rendered/internal-keycloak-stack.yaml`만 control-plane으로 전달해도 됩니다.

원본을 변경했으면 개발 PC의 저장소 루트에서 `make k8s-export`로 전달용 파일을
갱신합니다. 서버 기동과 claim 등록은 각각 별도 파일로 생성됩니다.

```bash
kubectl apply -f internal-keycloak-stack.yaml
```

레포를 control-plane에 전달한 경우 저장소 루트에서 아래 명령을 사용합니다.

```bash
kubectl kustomize deploy/keycloak/k8s >/dev/null
kubectl apply -k deploy/keycloak/k8s
```

이 스택에는 claim 등록 Job이 포함되지 않습니다. 사내 OIDC 설정 후 7절에서 별도
실행합니다. 이전 버전의 완료된 Job이 남아 있어도 서버 기동에는 영향을 주지 않습니다.

Kustomize는 사내 mirror의 다음 이미지를 사용합니다.

```text
repository.samsungds.net/proxy-docker-quay.io/keycloak/keycloak:26.7.1
repository.samsungds.net/proxy-docker-registry-1.docker.io/postgres:16
repository.samsungds.net/proxy-docker-registry-1.docker.io/traefik:v3.7.1
```

## 5. 배포 확인

```bash
kubectl get pv keycloak-postgres-data
kubectl get pvc -n etch-sso keycloak-postgres-data
kubectl rollout status statefulset/keycloak-postgres -n etch-sso --timeout=5m
kubectl rollout status deployment/keycloak -n etch-sso --timeout=10m
kubectl rollout status deployment/traefik -n etch-sso --timeout=5m
kubectl get pods -n etch-sso -o wide
kubectl get ingress -n etch-sso
```

세 Pod의 `NODE`가 모두 `khplane01w09`인지 확인합니다. 오류가 나면 event와 로그를
확인합니다.

```bash
kubectl get events -n etch-sso --sort-by=.lastTimestamp
kubectl logs -n etch-sso statefulset/keycloak-postgres
kubectl logs -n etch-sso deployment/keycloak
kubectl logs -n etch-sso deployment/traefik
```

외부 DNS/TLS가 연결되면 discovery endpoint를 확인합니다.

```bash
curl -fsS https://etch-sso.samsungds.net/realms/etch/.well-known/openid-configuration
```

초기 realm import는 `etch` realm이 DB에 없을 때만 실행됩니다. 이후
`k8s/server/etch-realm.json`을 수정해도 기존 realm을 자동으로 덮어쓰지 않으므로 운영 변경은
Keycloak Admin Console 또는 별도 관리 절차로 적용합니다.

## 6. 사내 OIDC client 발급

Keycloak에 등록할 사내 OIDC Identity Provider alias는 `oidc`를 사용합니다. 사내 OIDC
client 발급 시 callback/redirect URI에는 아래 주소를 정확히 등록합니다.

```text
운영: https://etch-sso.samsungds.net/realms/etch/broker/oidc/endpoint
Stage: https://stg.etch-sso.samsungds.net/realms/etch/broker/oidc/endpoint
```

운영과 Stage는 각각 별도 OIDC client ID와 secret을 발급받습니다. 프로토콜은
OpenID Connect, flow는 Authorization Code를 사용합니다.

### 사내 OIDC 접속 설정을 env로 적용하기

관리 화면에서 이미 연결한 설정은 서버 YAML을 적용해도 유지됩니다. env를 설정 원본으로
전환하거나 새 연결을 만들 때만 `deploy/keycloak/env/prod.env`의 `CORP_OIDC_*` 부분을 작성합니다.
인프라에서 확인한 client 인증 방식과 기존 서버의 서명 검증 정책을 명시합니다.
서명 검증을 켜면 JWKS URL도 필요합니다. discovery 없이 명시적 endpoint를 사용합니다.

```bash
make env-check APP=keycloak PROFILE=prod COMPONENT=oidc
make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc
kubectl delete job keycloak-oidc-setup -n etch-sso --ignore-not-found
kubectl apply -f deploy/keycloak/k8s/oidc/oidc-setup-job.yaml
kubectl wait --for=condition=complete job/keycloak-oidc-setup -n etch-sso --timeout=15m
kubectl logs job/keycloak-oidc-setup -n etch-sso
```

이 Job은 alias `oidc`를 생성하거나 지정한 연결값을 갱신합니다. 사용자나 realm은 삭제하지
않습니다. 선택적인 UserInfo/logout URL을 비우면 기존 설정을 유지합니다. 기존 연결이
정상이라면 이 단계는 생략하고 claim 등록부터 실행해도 됩니다.

## 7. 사내 OIDC 사용자 claim 일괄 매핑

`keycloak-oidc-claim-mappers` Job은 기존 `oidc` Identity Provider의 접속 설정을
변경하지 않고 다음 16개 claim을 동기화합니다. 일반 속성 mapper 15개와
EPID를 기본 username으로 지정하는 `epid-username` mapper 1개를 사용합니다(총 16개).

```text
loginid userid sabun username username_en
givenname surname deptname deptid mail grdName grdname_en busname
intcode intname employeetype
```

User Profile은 `k8s/claims/account-user-profile.json`으로 교체합니다. 기존 커스텀 정의를 합치지 않고
프로젝트의 `account_user` 신원 필드에 맞춥니다. Keycloak 기본 `username`, `email`은 유지합니다.
성·이름은 기본 `firstName`, `lastName`을 사용하고 커스텀 `givenname`, `surname` 정의는 제거합니다.
전체 16개 필드는 `view: [admin, user]`로 설정하여 사용자가 계정 화면에서 본인 정보를
조회할 수 있게 합니다. 편집은 `edit: [admin]`으로 관리자만 허용합니다. 미정의 과거 속성은
`ADMIN_EDIT`로 관리합니다. 조회 권한 변경은 최신 claim Job 재실행으로 반영합니다.
비밀번호·권한·로그인 시각은 프로필에 복제하지 않습니다.
사용자 레코드나 과거 속성값을 일괄 삭제·이관하는 작업은 수행하지 않습니다.

| 사내 claim / Portal token | Keycloak User Profile | account_user |
| --- | --- | --- |
| loginid | knox_id | knox_id |
| userid (EPID) | username (기본 속성) | avatarid |
| username | display_name | username |
| deptname | department | department |
| mail | email (기본 속성) | email |
| givenname | firstName (기본 속성) | givenname |
| surname | lastName (기본 속성) | surname |
| grdName | grd_name | grd_name |
| 나머지 8개 | claim과 같은 이름 | 같은 이름 |

예를 들어 사내 `userid=90000001`, `loginid=hong.gildong`, `username=홍길동`이면
Keycloak 기본 `username=90000001`, `knox_id=hong.gildong`,
`display_name=홍길동`으로 저장합니다. Portal token의 `username`은 계속 사람 이름인
`홍길동`이며 `userid`는 EPID입니다. 사내 `givenname`은 기본 `firstName`에, `surname`은
기본 `lastName`에 저장합니다. 기존 이름의 IdP mapper를 갱신하며 사내 재로그인 때 반영됩니다.
Portal token의 `givenname`·`surname`은 기본 property에서 읽어 기존 claim 이름으로 전달합니다.
과거 커스텀 속성값은 일괄 삭제하지 않으며 새 mapper에서 읽지 않습니다. 사내 응답에 없는 `first_name`·`last_name`은
수집·발급하지 않으며 기존 IdP·Portal client mapper도 각 Job 실행 시 제거합니다.
`username`을 성·이름으로 분리하지 않습니다. 기존 사용자 값과 공유 `profile` scope의
표준 mapper는 유지합니다. 기본 필드가 채워지면 `given_name`·`family_name`·`name`에도
해당 이름이 반영될 수 있습니다.
기본 필드의 프로필 정책은 [Keycloak User Profile 문서](https://www.keycloak.org/docs/latest/server_admin/#user-profile)를 참고합니다.

`epid-username`은 Username Template Importer(`oidc-username-idp-mapper`)이며
`template=${CLAIM.userid}`, `target=LOCAL`, `syncMode=FORCE`를 사용합니다. 사용자가 확인한
EPID의 유일성·불변성·재사용 금지를 전제로 하며 사내 로그인 응답에 `userid`가 있어야 합니다.
기존에 사내 IdP와 연결된 계정은 재로그인 때 같은 Keycloak 사용자 ID와 broker 연결을 유지한 채
username을 EPID로 갱신합니다. Job 자체가 모든 사용자 레코드를 일괄 변경하지는 않습니다.
`avatarid` 프로필 정의와 기존 IdP `userid` 속성 mapper는 제거합니다. EPID는 기본 username에만
저장하며 Portal token의 `userid`는 이 property를 읽습니다. 기존 avatarid 값은 일괄 삭제하지 않습니다.
Keycloak부터 정비하며 Django의 avatarid 컬럼과 프론트엔드는 후속 정비 대상으로 둡니다.
`knox_id`, 사번과 사람 이름 매핑은 유지합니다. 기본 `profile` client scope를 쓰는
다른 앱은 `preferred_username`에서 EPID를 보게 될 수 있습니다.

realm의 `Email as username`이 켜져 있으면 EPID mapper가 무시될 수 있어 Job이 변경 전에
중단합니다. 해당 옵션을 확인하고, 기존에 수동 생성한 계정의 username이 다른 사람의 EPID와
충돌하지 않는지도 전환 전에 확인합니다. 사내 IdP의 broker ID 설정은 변경하지 않습니다.

Identity Provider mapper는 `FORCE`로 설정합니다. 사내 OIDC를 거쳐 로그인해야 새 속성이
채워지며, 프로필 정의를 등록하는 것만으로 외부에서 제공되지 않은 값이 생기지는 않습니다.
Portal token mapper는 8절의 앱 client 등록 Job이 담당하며 기존 claim 이름을 유지합니다.

Job 실행 전 `etch` realm의 alias `oidc`와 `keycloak-runtime` 관리자 계정을 확인합니다.
Portal client는 없어도 됩니다. 개발 PC에서 `make k8s-export` 후
`deploy/keycloak/rendered/internal-keycloak-claim-mappers.yaml` 하나를 CP1으로 전달합니다.
이 파일에는 최신 스크립트·프로필 ConfigMap과 Job이 함께 들어 있어 스택 전체를 재적용할
필요가 없습니다. Ingress·Traefik·Keycloak Deployment는 포함하지 않습니다.

CP1에서 한 줄씩 실행합니다.

```bash
kubectl delete job keycloak-oidc-claim-mappers -n etch-sso --ignore-not-found
kubectl apply -f internal-keycloak-claim-mappers.yaml
kubectl logs -f job/keycloak-oidc-claim-mappers -n etch-sso --pod-running-timeout=120s
kubectl wait --for=condition=complete job/keycloak-oidc-claim-mappers -n etch-sso --timeout=15m
```

실패한 Pod 로그를 확인할 수 있도록 `restartPolicy: Never`, `backoffLimit: 0`을 사용합니다.
원인을 수정한 뒤 같은 삭제·적용 명령으로 재실행합니다. 원본 Job YAML만 적용할 때는
ConfigMap에 최신 `account-user-profile.json`과 스크립트가 먼저 준비돼 있어야 합니다.

사내 claim이 Portal까지 전달되려면 IdP Job 완료 후 8절의 Portal client Job도 재실행합니다.
두 작업 사이에는 로그인·토큰의 속성 구성이 다를 수 있으므로 연속 적용하고 재로그인합니다.
기존 client의 secret·callback도 입력값으로 갱신되므로 기존 운영값과 맞는지 확인합니다.

`Realm settings → User profile → Attributes`에서 정의를, 사내 재로그인 후
`Users → 사용자 선택 → Attributes`에서 실제 커스텀 값을 확인합니다. 기본 이메일은
사용자 기본 정보에서 확인합니다. Keycloak 세션만 재사용하면 새 사내 정보가 반영되지 않습니다.

Job이 실패하면 기존 Identity Provider alias와 관리자 계정을 먼저 확인합니다.

```bash
kubectl logs job/keycloak-oidc-claim-mappers -n etch-sso
kubectl get job keycloak-oidc-claim-mappers -n etch-sso
```

## 8. Portal API 연결

Portal의 실제 입력은 `deploy/portal/env/prod/api.env`에 작성합니다. 예시는 같은 경로의
`api.env.example`입니다. 기존 파일이 있으면 덮어쓰지 않습니다. client는
[Portal client 등록 절차](../portal/k8s/jobs/keycloak-client/README.md)로 별도 생성·갱신하며,
API Secret과 client 등록 작업이 같은 env 파일을 읽습니다.

```dotenv
OIDC_PROVIDER=keycloak
OIDC_CLIENT_ID=portal
OIDC_CLIENT_SECRET=<Portal 전용 client secret>
OIDC_ISSUER=https://etch-sso.samsungds.net/realms/etch
ADFS_AUTH_URL=https://etch-sso.samsungds.net/realms/etch/protocol/openid-connect/auth
ADFS_LOGOUT_URL=https://etch-sso.samsungds.net/realms/etch/protocol/openid-connect/logout
OIDC_REDIRECT_URI=https://<Portal DNS>/auth/keycloak/callback/
OIDC_TOKEN_URL=http://keycloak.etch-sso.svc.cluster.local:8080/realms/etch/protocol/openid-connect/token
OIDC_JWKS_URL=http://keycloak.etch-sso.svc.cluster.local:8080/realms/etch/protocol/openid-connect/certs
```

공개 issuer/DNS와 내부 token/JWKS URL을 서로 바꾸지 않습니다.

기존 `etch` realm은 초기 import에서 덮어쓰지 않으므로 등록된 사용자와 Portal client는
유지됩니다. 기존 클러스터를 새 구조로 바꿀 때 realm이나 PostgreSQL PVC를 삭제할 필요가 없습니다.

직급은 `grdName → grd_name → grdName` 매핑을 복원하며 `grdname_en`도 유지합니다.
`origincomp`는 계속 프로필에서 제외하고 각 Job이 기존 mapper를 삭제합니다.
기존 사용자 속성값과 Django DB 컬럼은 일괄 삭제하지 않습니다.
직급 반영은 두 Job을 재실행하고 사내 재로그인한 뒤 확인합니다.
