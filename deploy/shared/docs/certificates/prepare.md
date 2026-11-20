# 인증서 원본 준비

[가이드 홈](../README.md#https인증서) · 다음: [추출·검증](extract.md) → [공용 TLS 등록](../../../README.md#공용-tls-등록) → [등록 뒤 확인](apply.md)

**목적:** 발급받은 인증서 원본과 사내 CA를 관리 호스트의 정해진 폴더에 배치합니다.
**준비물:** 사이트별 PFX·P7B 파일과 PFX 비밀번호 파일, `SECDS-T2IssuingCA.crt`·`SECDS-T2RootCA.crt`, 관리 호스트의 저장소 checkout과 OpenSSL. 발급물과 비밀번호를 받는 방법은 [인증서 발급](../infrastructure/access.md#인증서-발급)에 있습니다.
**실행 위치:** 관리 호스트의 Bash, `Makefile`과 `deploy/`가 있는 저장소 루트.

## 파일 구조

```text
deploy/shared/certs/
├── README.md, .gitignore
├── sso.etch.samsungds.net/        # Keycloak 인증서
│   ├── sso.etch.samsungds.net.p7b  # 발급 원본(공개 인증서 묶음)
│   ├── sso.etch.samsungds.net.pfx  # 발급 원본(인증서·개인키)
│   ├── fullchain.crt               # 추출: 서버 인증서 + 중간 CA
│   ├── private.key                 # 추출: 개인키
│   ├── keycloak-ca-bundle.pem      # make ca-bundle이 만드는 사내 CA 묶음(OIDC·HTTPS 검증용)
│   └── backups/                    # 추출 시 기존 파일 보관
├── etch.samsungds.net/            # 공용 SAN 인증서(같은 구성, keycloak-ca-bundle.pem 제외)
└── ca/
    ├── SECDS-T2IssuingCA.crt       # 중간 CA
    └── SECDS-T2RootCA.crt          # 루트 CA
```

- 원본 PFX/P7B와 CA 파일 이름은 변경하지 않습니다. 도메인은 상위 폴더로 구분합니다.
- 공용 SAN 인증서를 쓰는 실제 공개 host는 [공용 TLS 등록](../../../README.md#공용-tls-등록)의 `TLS_HOST`로 지정합니다. 앱 배포의 준비 검사는 host를 SAN에 가진 `fullchain.crt`·`private.key`를 이 폴더들에서 찾아 자동으로 등록합니다.
- CA 파일은 추출 시 체인 검증, 실제 제공 인증서 확인, [사내 CA 묶음](../../../README.md#사내-ca-묶음) 생성에 사용합니다. 확장자만으로 PEM/DER 형식을 확정할 수 없으므로 명령이 두 형식을 모두 시도합니다.
- 실제 파일은 Git에 넣지 않습니다. Git으로 전송되지 않으므로 서버마다 별도로 배치합니다.

## 발급 원본 확보

[조회] 이미 있는 발급물과 사내 CA를 확인합니다.

```bash
ls -l deploy/shared/certs/sso.etch.samsungds.net/ deploy/shared/certs/etch.samsungds.net/ deploy/shared/certs/ca/
```

필요한 대상과 SAN은 [업무 HTTPS 인증서](../infrastructure/network.md#업무-https-인증서)와 대조합니다.
발급물이 없거나 SAN이 부족하면 [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 신청하고 발급물을 받습니다. PFX 비밀번호는 문서·응답·운영 기록에 쓰지 않고 [추출](extract.md)에서 쓰는 비밀번호 파일로만 전달받습니다.

## 1. 터미널 위치와 OpenSSL 확인

[조회]

```bash
pwd
ls -d Makefile deploy/shared/certs
openssl version
```

**기대 결과:** `Makefile`, `deploy/shared/certs`와 OpenSSL 버전이 표시됩니다.
**실패 확인:** 경로를 찾지 못하면 저장소 루트에서 실행했는지 확인합니다. `openssl: command not found`라면 [관리 호스트 sudo](../infrastructure/access.md#관리-호스트-sudo) 절의 방법으로 OpenSSL을 설치합니다.

## 2. 폴더 준비와 원본 배치

[변경] 폴더를 만들고 소유자만 접근하게 합니다.

```bash
mkdir -p deploy/shared/certs/{sso.etch.samsungds.net,etch.samsungds.net,ca}
chmod 700 deploy/shared/certs deploy/shared/certs/{sso.etch.samsungds.net,etch.samsungds.net,ca}
```

[변경] [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 받은 파일을 다음 위치에 둡니다. 다른 서버에서 가져올 때의 전송은 [파일 반입](../infrastructure/access.md#파일-반입) 절을 따릅니다.

| 넣을 폴더 | 원본 파일 |
| --- | --- |
| `deploy/shared/certs/sso.etch.samsungds.net/` | `sso.etch.samsungds.net.pfx`, `sso.etch.samsungds.net.p7b` |
| `deploy/shared/certs/etch.samsungds.net/` | `etch.samsungds.net.pfx`, `etch.samsungds.net.p7b` |
| `deploy/shared/certs/ca/` | `SECDS-T2IssuingCA.crt`, `SECDS-T2RootCA.crt` |

이미 추출한 `fullchain.crt`와 `private.key`를 사용하려면 해당 사이트 폴더에 함께 넣습니다.
아직 `fullchain.crt`, `private.key`, `keycloak-ca-bundle.pem`이 없어도 정상입니다.

## 3. 파일 권한 설정

[변경] PFX를 소유자만 읽게 하고 배치 결과를 확인합니다.

```bash
find deploy/shared/certs -name '*.pfx' -exec chmod 600 {} +
ls -l deploy/shared/certs/sso.etch.samsungds.net/ deploy/shared/certs/etch.samsungds.net/ deploy/shared/certs/ca/
```

**기대 결과:** 위 표의 파일이 표시되고 PFX의 권한이 `-rw-------`입니다. 파일은 배포 명령을 실행하는 계정이 읽을 수 있어야 하며, 추출한 개인키 권한은 추출 단계에서 설정됩니다.

## 다음 단계

- 원본에서 새로 추출: [추출·검증](extract.md)의 1 → 3
- 기존 결과 파일 사용: [추출·검증](extract.md)의 1 → 4
- 추출을 마치면 앱의 `make ops-deploy`가 준비 검사에서 공용 TLS를 등록합니다. 직접 등록은 [공용 TLS 등록](../../../README.md#공용-tls-등록), 등록 뒤 확인은 [인증서 적용](apply.md)입니다.
