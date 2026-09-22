# Keycloak 인증서 입력 폴더

프로젝트를 서버에 복사한 뒤 아래 파일을 이 폴더에 넣습니다.
이 README 외 파일과 하위 디렉터리는 모두 Git에서 제외합니다.

## 기동에 필요한 파일

| 파일명 | 내용 |
| --- | --- |
| `keycloak-fullchain.crt` | PEM 형식 서버 인증서 + Intermediate CA 체인, 서버 인증서가 맨 앞 |
| `keycloak.key` | 해당 인증서와 짝인 암호화되지 않은 PEM 개인키 |

접속 도메인은 현재 원본 기준 `etch-sso.samsungds.net`이며 인증서 SAN에 포함되어야 합니다.
파일을 넣는 곳은 kubectl을 실행하는 배포 서버입니다. worker에 개인키를 복사할 필요는 없습니다.

## PFX로 받은 경우

다음 원본 파일도 이 폴더에 보관할 수 있습니다.

| 파일명 예시 | 용도 |
| --- | --- |
| `etch-sso.samsungds.net.pfx` | 서버 인증서·개인키 추출 원본 |
| `SECDS-T2IssuingCA.crt` | Intermediate CA |
| `SECDS-T2RootCA.crt` | 체인 검증·클라이언트 신뢰용 Root CA |
| `etch-sso.samsungds.net.p7b` | 제공된 경우 CA 묶음 확인용 |

[TLS 가이드](../TLS.md)의 추출·검증 순서를 따르되, `/appdata/certs` 대신
이 프로젝트의 `deploy/keycloak/certs` 절대 경로를 사용합니다.
이미 fullchain과 개인키를 받았다면 PFX는 필요하지 않습니다.

## 입력 확인과 TLS Secret 등록

최초 등록·기동은 [Keycloak 배포 안내](../README.md)의 `make keycloak-check` →
`make keycloak-up`으로 처리할 수 있습니다. 아래 명령은 수동 검증·TLS 갱신이 필요할 때 사용합니다.

저장소 루트에서 실행합니다. 명령별 성공을 확인하고 다음 명령으로 진행합니다.

```bash
chmod 700 deploy/keycloak/certs
chmod 600 deploy/keycloak/certs/keycloak.key
openssl x509 -in deploy/keycloak/certs/keycloak-fullchain.crt \
  -noout -checkhost etch-sso.samsungds.net
openssl x509 -in deploy/keycloak/certs/keycloak-fullchain.crt -noout -checkend 0
```

인증서·개인키 일치와 전체 체인은 [TLS 가이드](../TLS.md)의 4절대로 확인합니다.
확인 후 대상 context를 명시하여 등록합니다. 기존 TLS Secret이 있으면 갱신합니다.

```bash
set -euo pipefail
read -r -p '배포할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
test -n "$KEYCLOAK_KUBE_CONTEXT"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" create namespace etch-sso --dry-run=client -o yaml |
  kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f -
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" create secret tls keycloak-tls \
  --namespace etch-sso \
  --cert=deploy/keycloak/certs/keycloak-fullchain.crt \
  --key=deploy/keycloak/certs/keycloak.key \
  --dry-run=client -o yaml |
  kubectl --context "$KEYCLOAK_KUBE_CONTEXT" apply -f -
```

이 명령은 TLS Secret만 등록합니다. env 등록과 Keycloak 기동은
[배포 안내](../README.md)의 별도 단계입니다. 폴더 복사만으로 Secret이 자동 등록되지는 않습니다.
