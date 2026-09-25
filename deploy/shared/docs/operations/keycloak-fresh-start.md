# 같은 클러스터에서 Keycloak을 빈 DB로 재기동

> 과거 특정 작업의 일회성 재설치 기록입니다. 아래의 사용자 요청·삭제 허용은 당시 작업에만 해당합니다.
> 신규 설치·정기 업데이트·일반 장애 복구에 재사용하지 않습니다. 현재 시작점은 [Kubernetes 가이드](../kubernetes/README.md)입니다.

기존 Kubernetes Keycloak을 중지하고 이 프로젝트 원본으로 다시 시작하는 절차입니다.
Keycloak 사용자·realm·client·사내 OIDC 설정은 새 DB에 승계하지 않습니다.
Airflow DB는 초기화하지 않습니다. 기본 절차에서는 기존 Keycloak 데이터를 복구용으로 별도 보관합니다.
이번 재설치는 사용자 요청에 따라 3절의 일회성 삭제 절차를 사용해 DB 보관을 생략합니다.

## 1. 중지 전 준비 (CP1 / 배포용 checkout)

[Keycloak 안내](../../../keycloak/README.md)의 env·인증서·worker 디스크 준비를 먼저 마칩니다.
Airflow 준비와 배포는 이후 별도 단계입니다.
현재 작업 폴더의 미커밋·미추적 파일은 Git clone/pull로 전달되지 않습니다.
검증한 배포 파일이 서버에도 모두 있는지 확인합니다.

```bash
set -euo pipefail
read -r -p '배포할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
export KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment,statefulset,pod,pvc -o wide
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" get pv keycloak-postgres-data -o yaml
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get statefulset keycloak-postgres -o yaml
```

실제 리소스 이름이 `keycloak`, `keycloak-postgres`인지 확인합니다.
이 문서의 worker 경로는 원본의 `khplane01w09`, `/appdata/keycloak-postgres` 및
`PGDATA=/var/lib/postgresql/data/pgdata` 기준입니다. 실제 PV·마운트·PGDATA가 다르면
아래 파일 이동 명령을 실행하지 말고 실제 배치에 맞는 절차를 먼저 작성합니다.
GitOps 또는 다른 운영 도구가 replicas를 자동 복구한다면 작업 동안 해당 동기화를 중지합니다.

Keycloak의 `deploy/keycloak/env/prod.env`에서 일반 설정과 신규 DB 비밀번호·bootstrap 관리자 비밀번호를 함께 입력합니다.
기존 도메인과 TLS는 유지합니다. 기존 Secret은 아래 백업이 끝나기 전에 갱신하지 않습니다.
사내 로그인을 사용하려면 같은 파일의 `CORP_OIDC_*`도 실제 발급값으로 준비합니다.

```bash
make server-check APP=keycloak
bash deploy/shared/scripts/check-env.sh keycloak prod server deploy/keycloak/env/prod.env
bash deploy/shared/scripts/check-env.sh keycloak prod oidc deploy/keycloak/env/prod.env
```

VIP 첫 구성이라면 실제 `make keycloak-check`와 `make keycloak-up`에
`VIP_BACKENDS=10.172.40.117,10.172.40.87`을 추가합니다.
이 IP는 [현재 VIP 구성](../../ingress/VIP.md)에만 해당합니다.
기존 TLS Secret과 동일한 인증서·개인키를 `deploy/shared/certs/etch-sso.samsungds.net/`에 준비하고
[인증서 안내](../../certs/README.md)의 도메인·기간·키·체인 검사를 마칩니다.
새 credential은 기존 Secret과 다르므로 `keycloak-check`는 4절의 명시적 Secret 갱신 후 실행합니다.

검사 통과는 실제 이미지 pull·DB 초기화·로그인 성공을 보장하지 않습니다.
worker가 Keycloak·PostgreSQL·Traefik 이미지를 가져올 수 있는지 먼저 확인합니다.

## 2. 설정 보관 후 중지 (CP1)

```bash
umask 077
KEYCLOAK_BACKUP_DIR="$(mktemp -d /var/tmp/keycloak-before-reset.XXXXXX)"
printf '설정 백업 경로: %s\n' "$KEYCLOAK_BACKUP_DIR"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get secret keycloak-runtime -o yaml \
  > "$KEYCLOAK_BACKUP_DIR/keycloak-runtime.yaml"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak -o yaml \
  > "$KEYCLOAK_BACKUP_DIR/keycloak-deployment.yaml"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get statefulset keycloak-postgres -o yaml \
  > "$KEYCLOAK_BACKUP_DIR/keycloak-postgres.yaml"

kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso scale deployment/keycloak --replicas=0
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso wait --for=delete pod \
  -l app.kubernetes.io/name=keycloak --timeout=180s
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso scale statefulset/keycloak-postgres --replicas=0
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso wait --for=delete pod \
  -l app.kubernetes.io/name=keycloak-postgres --timeout=180s
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods -o wide
```

Keycloak과 DB Pod가 모두 사라졌는지 확인한 후 다음 단계로 진행합니다.
Secret 백업에는 비밀값이 있으므로 접근을 제한하고 저장소 밖에 보관합니다.
Namespace·PV·PVC·Traefik·TLS Secret은 삭제하지 않습니다.

## 3. 기존 DB 디렉터리 분리 (앱 worker)

이 명령은 CP1이 아니라 **PV가 있는 `khplane01w09` worker**에서 실행합니다.
DB Pod가 중지되었고 이 경로를 다른 프로세스가 사용하지 않는 상태여야 합니다.

### 이번 재설치만: 보관 없이 삭제 후 재생성

아래 명령을 실행하고 4절로 진행합니다. 기존 DB를 남긴 채 manifest만 덮어쓰면
빈 DB가 되지 않으므로 `pgdata`를 삭제합니다. 기존 사용자·realm·client는 이 데이터에서 복구할 수 없습니다.
2절의 설정 백업과 Pod 중지 확인은 그대로 수행합니다.

```bash
set -euo pipefail
test "$(sudo readlink -f /appdata/keycloak-postgres/pgdata)" = /appdata/keycloak-postgres/pgdata
sudo test -f /appdata/keycloak-postgres/pgdata/PG_VERSION
if sudo mountpoint -q /appdata/keycloak-postgres/pgdata; then
  echo 'pgdata 자체가 마운트 지점입니다. 실제 저장소 구성을 확인하세요.' >&2
  exit 1
fi
sudo rm -rf --one-file-system -- /appdata/keycloak-postgres/pgdata
sudo test ! -e /appdata/keycloak-postgres/pgdata
```

PV 상위 디렉터리는 유지하며 PostgreSQL이 다음 기동 때 새 `pgdata`를 생성합니다.
이 일회성 예외는 이후 재배포에서 반복하지 않습니다.

### 기본 절차: 기존 DB 보관

이번 재설치에서는 아래 보관 명령을 실행하지 않습니다.

```bash
set -euo pipefail
sudo test -d /appdata/keycloak-postgres/pgdata
KEYCLOAK_DATA_BACKUP="$(sudo mktemp -d /appdata/keycloak-postgres-before-reset.XXXXXX)"
sudo mv -- /appdata/keycloak-postgres/pgdata "$KEYCLOAK_DATA_BACKUP/pgdata"
printf '이전 DB 보관 경로: %s\n' "$KEYCLOAK_DATA_BACKUP"
sudo test ! -e /appdata/keycloak-postgres/pgdata
```

PV의 상위 디렉터리는 그대로 두고 `pgdata`만 옮깁니다. 새 `pgdata`는 PostgreSQL이 생성합니다.
보관 경로를 운영 기록에 남깁니다. 같은 디스크의 사본은 디스크 장애 대비 백업이 아니므로
복구가 필요하면 별도 저장매체에도 보관합니다.

## 4. 신규 Secret 등록 및 프로젝트 구성 적용 (CP1)

Secret 등록 도구도 지정한 context를 사용하도록 임시 wrapper를 만듭니다.
아래 명령은 1단계의 `KEYCLOAK_KUBE_CONTEXT`가 export된 같은 shell에서 실행합니다.

```bash
KEYCLOAK_KUBECTL_DIR="$(mktemp -d /tmp/keycloak-kubectl.XXXXXX)"
cat > "$KEYCLOAK_KUBECTL_DIR/kubectl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec kubectl --context "${KEYCLOAK_KUBE_CONTEXT:?context 필요}" "$@"
SH
chmod 700 "$KEYCLOAK_KUBECTL_DIR/kubectl"
export KUBECTL_BIN="$KEYCLOAK_KUBECTL_DIR/kubectl"
bash deploy/shared/scripts/apply-env.sh keycloak prod server deploy/keycloak/env/prod.env

make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`keycloak-up`은 남겨둔 리소스를 프로젝트 manifest로 재적용해 앱과 DB replicas를 1로 복구합니다.
새 PostgreSQL DB → Keycloak realm import 순서로 준비합니다.
기존 Traefik 감시 namespace와 VIP 배치는 유지합니다.
공용 라우팅을 연결한 서버에서는 단독 `kubectl apply -k deploy/keycloak/k8s`로 대체하지 않습니다.

## 5. 사내 OIDC와 claim 재등록 (CP1)

초기 `etch-realm.json`에는 사내 IdP와 앱 client가 없습니다.
새 DB에서는 기존 관리자 화면 설정도 없어지므로 아래 작업이 필요합니다.

```bash
bash deploy/shared/scripts/apply-env.sh keycloak prod oidc deploy/keycloak/env/prod.env
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso delete job keycloak-oidc-setup --ignore-not-found
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f deploy/keycloak/k8s/oidc/oidc-setup-job.yaml
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso wait \
  --for=condition=complete job/keycloak-oidc-setup --timeout=15m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-oidc-setup

kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso delete job keycloak-oidc-claim-mappers --ignore-not-found
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f deploy/keycloak/k8s/claims/claim-mappers-job.yaml
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso wait \
  --for=condition=complete job/keycloak-oidc-claim-mappers --timeout=15m
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-oidc-claim-mappers
```

Portal 등 기존 앱이 사용하던 client는 별도 재등록해야 합니다.
Portal client 절차는 [client 등록 안내](../../../portal/k8s/jobs/keycloak-client/README.md)를 따릅니다.
Airflow는 현재 자체 관리자 계정으로 로그인하며 이 절차가 Airflow SSO를 설정하지는 않습니다.

## 6. 완료 판정

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods,pvc,ingress
curl --fail --show-error https://etch-sso.samsungds.net/realms/etch/.well-known/openid-configuration
```

사내 CA가 필요하면 `--cacert /실제/사내-ca.pem`을 지정합니다.
Keycloak 관리자 로그인·etch realm·OIDC 설정·실제 사내 로그인과 claim 값까지 확인합니다.
Keycloak 검증을 마친 뒤 [Airflow 안내](../../../airflow/README.md)에 따라 별도로 배포합니다.

실패 시 namespace·PV를 삭제하거나 이전 데이터를 새 DB에 합치지 않습니다.
기존 DB를 보관한 경우 복구하려면 Keycloak과 DB를 다시 중지하고 새 `pgdata`를 별도 분리한 뒤 기존 디렉터리와
이전 DB 비밀번호·이미지·배포 설정을 함께 복원하는 별도 절차를 수행합니다.
이번처럼 보관 없이 삭제했다면 기존 DB 복구에는 별도로 보유한 백업이 필요합니다.
