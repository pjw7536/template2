# Headlamp 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/headlamp/README.md) · [준비](../../../../deploy/headlamp/docs/01-prepare.md) · [인증](../../../../deploy/headlamp/docs/02-authentication.md) · [배포](../../../../deploy/headlamp/docs/03-deploy.md) · [운영](../../../../deploy/headlamp/docs/04-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `headlamp` (Helm release `headlamp`) |
| 공개 주소 | `https://headlamp.etch.samsungds.net` (Keycloak realm `etch`, client `headlamp`) |
| 고정 이름 | client secret Secret `headlamp/headlamp-oidc`, CA ConfigMap `headlamp/headlamp-oidc-ca` |
| 인증서·CA 파일 | 사이트 `deploy/shared/certs/etch.samsungds.net/`, CA 원본 `deploy/shared/certs/ca/`, Keycloak CA 묶음 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |
| 배포 명령 | `make headlamp-check` → `make headlamp-up` (성공 시 배포 기록 자동) |
| 완료 기준 | Pod Ready, RBAC 검사 기대값 일치, 사람이 관리자 로그인 성공·그룹 밖 계정 거부 확인. Pod Ready만으로 완료가 아님 |
| 먼저 필요한 것 | Keycloak 운영, 모든 제어면 API server OIDC 설정, 업무 도메인 TLS |

## 사람이 해야 하는 일

- [사람] 인증서 파일 배치: `deploy/shared/certs/etch.samsungds.net/fullchain.crt`·`private.key`, `deploy/shared/certs/ca/SECDS-T2RootCA.crt`·`SECDS-T2IssuingCA.crt`
- [사람] Keycloak Admin Console: client 가져오기·대조, `headlamp-admins` 그룹과 가입자, Credentials의 secret 확인(Regenerate 금지)
- [사람] client secret 입력([client secret 등록](../../../../deploy/headlamp/docs/02-authentication.md#5-관리-호스트에서-client-secret-등록))
- [사람] 모든 제어면의 API server OIDC 설정([API server OIDC](../../../../deploy/shared/docs/kubernetes/oidc.md), 제어면 담당자)
- [사람] DNS·방화벽, 브라우저 로그인 확인(관리자 계정·그룹 밖 계정)

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `HEADLAMP_ENV` | Headlamp env 경로 | `deploy/headlamp/env/k8s.env` |
| `HEADLAMP_OIDC_CA_FILE` | OIDC 검사용 Keycloak CA 묶음 | `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem` |

## A. 최초 설치

1. [조회] Keycloak·Traefik 확인
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n etch-sso get deployment keycloak traefik
   kubectl --context kubernetes-admin@kubernetes get ingressclass traefik
   ```
   성공: 두 Deployment READY가 같은 숫자, IngressClass 조회됨.
2. [검사] env 계산값 확인
   ```bash
   make -s headlamp-setup-env
   ```
   성공: `HEADLAMP_SSO_HOST=sso.etch.samsungds.net`과 `HEADLAMP_CALLBACK_URL=https://headlamp.etch.samsungds.net/oidc-callback`이 출력됨. 다르면 이 런북의 고정 경로가 맞지 않으므로 멈추고 보고합니다.
3. [변경] chart 준비(로컬 파일)와 [검사] 원본 검사
   ```bash
   make headlamp-fetch-chart
   make headlamp-check
   ```
   성공: `chart 준비 완료:`, `서버 원본 검사 통과: headlamp/prod`. SHA-256 불일치면 멈춥니다.
4. [변경] namespace(승인 필요)
   ```bash
   kubectl --context kubernetes-admin@kubernetes create namespace headlamp --dry-run=client -o yaml | kubectl --context kubernetes-admin@kubernetes apply -f -
   kubectl --context kubernetes-admin@kubernetes get namespace headlamp
   ```
   성공: `Active`. `Terminating`이면 멈춥니다.
5. [조회] 인증서 파일 확인
   ```bash
   ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt deploy/shared/certs/etch.samsungds.net/private.key deploy/shared/certs/ca/SECDS-T2RootCA.crt deploy/shared/certs/ca/SECDS-T2IssuingCA.crt
   ```
   하나라도 없으면 [사람]에게 배치를 요청하고 멈춥니다.
6. [변경] Keycloak CA 묶음 생성(로컬 파일, 승인 필요)
   ```bash
   bash -c 'set -euo pipefail; umask 077; work=$(mktemp -d); trap "rm -rf $work" EXIT; mkdir -p deploy/shared/certs/sso.etch.samsungds.net; for ca in SECDS-T2RootCA SECDS-T2IssuingCA; do openssl x509 -inform PEM -in deploy/shared/certs/ca/$ca.crt -out $work/$ca.pem 2>/dev/null || openssl x509 -inform DER -in deploy/shared/certs/ca/$ca.crt -out $work/$ca.pem; done; cat $work/SECDS-T2RootCA.pem $work/SECDS-T2IssuingCA.pem > $work/ca.pem; install -m 0644 $work/ca.pem deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem; echo "CA 묶음 생성 완료"'
   openssl crl2pkcs7 -nocrl -certfile deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem | openssl pkcs7 -print_certs -noout
   ```
   성공: `CA 묶음 생성 완료`와 subject 두 줄.
7. [변경] 공용 TLS: `headlamp.etch.samsungds.net`을 사이트 폴더 `etch.samsungds.net`으로 [공통 TLS 등록](00-common.md#공용-tls-등록)한 뒤 [공통 Traefik 갱신](00-common.md#공용-traefik-검사갱신)의 `ingress-up`을 합니다.
8. [변경] CA ConfigMap(승인 필요)과 [검사] OIDC 연결 검사
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n headlamp create configmap headlamp-oidc-ca --from-file=ca.crt=deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem --dry-run=client -o yaml | kubectl --context kubernetes-admin@kubernetes apply -f -
   make headlamp-oidc-check HEADLAMP_OIDC_CA_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem"
   ```
   성공: `OIDC 연결 검사 통과`. 실패하면 DNS·방화벽·CA·issuer 문제이므로 멈춥니다.
9. [조회] client 등록 파일 생성
   ```bash
   make -s headlamp-oidc-client > /tmp/headlamp-client.json
   ```
   [사람] 이 파일로 Keycloak client 가져오기·그룹·secret 확인을 요청합니다([Keycloak client와 관리자](../../../../deploy/headlamp/docs/02-authentication.md#keycloak-client와-관리자)).
10. [사람] client secret 등록을 요청합니다. 완료 후 확인합니다.
    ```bash
    kubectl --context kubernetes-admin@kubernetes -n headlamp get secret headlamp-oidc
    ```
    성공: `Opaque`, DATA `1`.
11. [사람] 제어면 API server OIDC 반영을 요청합니다. 완료 답을 받으면 확인합니다.
    ```bash
    kubectl --context kubernetes-admin@kubernetes get --raw=/readyz
    ```
    성공: `ok`.
12. [변경] 배포(승인 필요)
    ```bash
    make headlamp-check
    make headlamp-up KUBE_CONTEXT=kubernetes-admin@kubernetes
    ```
    성공: `접속 주소: https://headlamp.etch.samsungds.net/`와 `배포 기록 저장: headlamp/deploy-record-headlamp`.
13. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
14. [사람] 관리자 계정 로그인과 그룹 밖 계정 거부 확인을 요청합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·chart·이미지 | A-3 → A-12 → C → [사람] 로그인 확인 |
| client secret·CA 갱신 | 사람이 다시 등록한 뒤 아래 재시작 블록 |
| 사이트 인증서 | A-7 |
| Keycloak CA 변경 | 멈추고 사람에게 묻기(모든 API server CA도 갱신 필요) |

[변경] 재시작(승인 필요). 설정이 같으면 `headlamp-up`만으로는 Pod가 다시 만들어지지 않습니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n headlamp rollout restart deployment/headlamp
kubectl --context kubernetes-admin@kubernetes -n headlamp rollout status deployment/headlamp --timeout=180s
```

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n headlamp get deployment,pods,svc,ingress
kubectl --context kubernetes-admin@kubernetes auth can-i list nodes --as=headlamp:rbac-probe --as-group=headlamp:/headlamp-admins --as-group=system:authenticated
kubectl --context kubernetes-admin@kubernetes auth can-i list nodes --as=headlamp:rbac-outsider --as-group=system:authenticated
curl --fail --silent --show-error --cacert deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem https://headlamp.etch.samsungds.net/ -o /dev/null && echo 'Headlamp HTTPS 응답 확인 완료'
make drift-check APP=headlamp KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: Deployment `1/1`, 첫 `auth can-i`는 `yes`, 두 번째는 `no`, HTTPS 응답 확인, drift-check 종료 코드 `0`. 404면 Ingress·Traefik 감시, 503이면 Pod·Service 문제입니다.

## 멈추고 사람에게 묻는 조건

- `headlamp-setup-env` 출력이 이 런북의 고정 값과 다름
- chart SHA-256 불일치, OIDC 검사 실패
- 로그인 후 401(API server OIDC) 또는 403(그룹·mapper)
- 기존 `headlamp-oidc` Secret에 다른 키가 있음, `cannot impersonate` 오류
- client secret Regenerate, replica 증가, `helm rollback`이 필요해 보이는 경우. 실행하지 않습니다.
