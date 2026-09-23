# Keycloak HTTPS 인증서 적용

[Keycloak 배포 안내](README.md) · [공용 인증서 추출·검증·적용](../shared/certs/README.md)

| 항목 | 운영값 |
| --- | --- |
| 도메인 | `etch-sso.samsungds.net` |
| 인증서 폴더 | `deploy/shared/certs/etch-sso.samsungds.net/` |
| 인증서·개인키 | `keycloak-fullchain.crt`, `keycloak.key` |
| TLS Secret | `etch-sso/keycloak-tls` |
| TLS 종료 | Traefik |

## 인증서 준비와 적용

[공용 인증서 안내](../shared/certs/README.md)의 **Keycloak 사이트 선택**을 사용합니다.
PFX·P7B 추출, fullchain 구성, 검증, TLS Secret 갱신과 실제 서버 인증서 확인을 한곳에서 관리합니다.
Keycloak의 개인키는 TLS를 종료하는 Traefik이 사용하며 API server용 CA 파일과는 다릅니다.

최초 앱 배포는 [운영 안내](README.md)의 `make keycloak-check` → `make keycloak-up`을 사용합니다.
두 명령은 위 인증서 폴더를 기본으로 사용합니다. 기존 TLS Secret과 파일이 다르면 중단하므로
**인증서 갱신은 공용 안내의 TLS Secret 등록 명령을 먼저 실행**합니다.
정상 반영되면 TLS 갱신만을 위해 Keycloak이나 Traefik을 재시작할 필요는 없습니다.

## 신뢰 설정의 구분

서버가 중간 인증서를 포함한 fullchain을 제공하고, 접속하는 PC·서버가 루트 CA를 신뢰해야 합니다.
CP1의 신뢰 설정은 PC·Headlamp Pod·Kubernetes API server에 자동으로 전달되지 않습니다.
Headlamp와 API server의 신뢰 설정은 [OIDC 가이드](../headlamp/OIDC.md)를 따릅니다.

## 클라이언트 신뢰: Ubuntu 클라이언트의 Root CA 신뢰

해당 서버가 HTTPS 클라이언트로 요청할 때 기본 신뢰 검증이 실패하는 경우에만 진행합니다.

```bash
curl -v https://etch-sso.samsungds.net/ -o /dev/null
```

`--cacert`를 지정하면 성공하고 위 요청은 신뢰 오류로 실패한다면 해당 노드에 Root CA를 등록합니다.

```bash
sudo install -m 0644 deploy/shared/certs/ca/SECDS-T2RootCA.crt \
  /usr/local/share/ca-certificates/SECDS-T2RootCA.crt

sudo update-ca-certificates

curl -v https://etch-sso.samsungds.net/ -o /dev/null
```

PEM 형식의 `.crt` 파일을 사용합니다. 신뢰가 필요한 CP1·Worker 각각에서 수행하며
Worker에는 Root CA 공개 인증서만 전달하면 됩니다. 호스트 OS 신뢰 저장소 변경이
컨테이너나 별도 Java/Python 저장소에 자동 적용되지는 않을 수 있습니다.
Pod 내부에서만 실패하면 해당 애플리케이션의 신뢰 저장소를 확인합니다.

## 클라이언트 신뢰: Windows 브라우저 경고 확인

`https://etch-sso.samsungds.net` 도메인으로 접속합니다. IP SAN이 없는 인증서에서
IP 주소로 접속하면 이름 불일치 경고가 발생할 수 있습니다.

- 현재 사용자 저장소: `Win + R` → `certmgr.msc`
- 로컬 컴퓨터 저장소: `Win + R` → `certlm.msc`

| 저장소 | 확인할 인증서 |
| --- | --- |
| 신뢰할 수 있는 루트 인증 기관 → 인증서 | `SECDS-T2RootCA` |
| 중간 인증 기관 → 인증서 | 필요 시 `SECDS-T2IssuingCA` |

서버가 Intermediate CA를 제공하면 PC에 중간 인증서를 반드시 따로 설치해야 하는 것은 아닙니다.
Root CA가 없다면 회사 인증서 배포 정책에 따라 설치하고 관리 PC의 GPO 배포 여부도 확인합니다.
서버 검증만으로 브라우저 경고 원인을 단정하지 말고 오류 코드와 실제 표시 인증서를 확인합니다.

| 증상 | 확인 항목 |
| --- | --- |
| `NET::ERR_CERT_AUTHORITY_INVALID` | Root CA 신뢰, Intermediate 누락, 보안 프록시 인증서 |
| `NET::ERR_CERT_COMMON_NAME_INVALID` | URL과 SAN, IP 접속, 기본 인증서 노출 |
| `NET::ERR_CERT_DATE_INVALID` | 유효기간, PC·서버 시간 |
| Traefik 기본 인증서 표시 | Ingress 도메인·Secret 참조, 실제 endpoint |
| 직접 IP 검증 성공, 브라우저만 실패 | PC DNS·LB·프록시 경로, 실제 인증서, 신뢰 정책 |
