# 인증서 원본과 파일 준비

[인증서 안내](README.md) · [원본 준비](01-prepare.md) · [추출·검증](02-extract.md) · [서버 적용](03-apply.md)

## 준비할 원본과 생성될 파일

```text
deploy/shared/certs/
├── README.md                  # 시작 안내
├── 01-prepare.md                 # 원본 파일 준비
├── 02-extract.md                 # 추출·검증
├── 03-apply.md                   # 서버 적용·갱신
├── .gitignore
├── etch-sso.samsungds.net/       # Keycloak
│   ├── .gitkeep
│   ├── etch-sso.samsungds.net.p7b
│   ├── etch-sso.samsungds.net.pfx
│   ├── fullchain.crt           # 1단계에서 생성
│   ├── private.key             # 1단계에서 생성
│   └── keycloak-ca-bundle.pem   # OIDC 가이드에서 나중에 생성
├── etch.samsungds.net/           # Headlamp 접속 도메인
│   ├── .gitkeep
│   ├── etch.samsungds.net.p7b
│   ├── etch.samsungds.net.pfx
│   ├── fullchain.crt           # 1단계에서 생성
│   └── private.key             # 1단계에서 생성
└── ca/                          # 공용 인증기관 원본
    ├── .gitkeep
    ├── SECDS-T2IssuingCA.crt
    └── SECDS-T2RootCA.crt
```

파일 이름은 위와 같이 유지합니다. 기존에 공용 폴더 바로 아래 넣었다면 위 구조에 맞춰 이동합니다.

`fullchain.crt`와 `private.key`는 1단계에서 생성합니다.
이미 추출한 파일이 있다면 새로 추출하는 대신 기존 파일을 검증한 뒤 서버 적용으로 진행합니다.

두 사이트 모두 인증서는 `fullchain.crt`, 개인키는 `private.key`입니다. 도메인은 상위 폴더로 구분합니다.
원본 PFX/P7B와 CA 파일 이름은 변경하지 않습니다.

| 보관 폴더 | 파일 | 용도 |
| --- | --- | --- |
| `etch-sso.samsungds.net/` | `etch-sso.samsungds.net.p7b`, `etch-sso.samsungds.net.pfx` | Keycloak 인증서 발급 원본 |
| `etch-sso.samsungds.net/` | `fullchain.crt` | Keycloak 서버 인증서와 중간 인증서 체인 |
| `etch-sso.samsungds.net/` | `private.key` | Keycloak 인증서와 짝인 개인키 |
| `ca/` | `SECDS-T2IssuingCA.crt` | 중간 인증기관 인증서 |
| `ca/` | `SECDS-T2RootCA.crt` | 루트 인증기관 인증서 |
| `etch.samsungds.net/` | `etch.samsungds.net.p7b`, `etch.samsungds.net.pfx` | Headlamp 접속 도메인의 인증서 발급 원본 |
| `etch.samsungds.net/` | `fullchain.crt` | Headlamp 서버 인증서와 중간 인증서 체인 |
| `etch.samsungds.net/` | `private.key` | Headlamp 인증서와 짝인 개인키 |

CA 파일은 나중에 Keycloak 인증서를 신뢰하기 위한 CA 묶음을 만들 때 사용합니다.
확장자만으로 PEM/DER 형식을 확정할 수 없으므로 실제 파일을 넣은 뒤 형식과 체인을 확인합니다.

## 사전 준비: 원본 파일 배치

### 준비 A. 터미널 위치와 OpenSSL 확인

CP1에 접속해 Bash 터미널을 열고, 저장소를 내려받은 폴더로 이동합니다.
이 문서의 모든 명령은 `Makefile`과 `deploy/`가 있는 **저장소 루트**를 기준으로 합니다.

```bash
pwd
ls -d Makefile deploy/shared/certs
openssl version
```

**확인할 결과:** `Makefile`, `deploy/shared/certs`와 OpenSSL 버전이 표시됩니다.
경로를 찾지 못하면 저장소 위치를 먼저 확인합니다. `openssl: command not found`라면 서버의 OpenSSL 설치가 필요합니다.

PFX 발급 시 받은 비밀번호도 준비합니다.

### 준비 B. 원본 파일 넣기

먼저 보관 폴더를 준비합니다. 이미 폴더가 있어도 아래 명령을 실행할 수 있습니다.

```bash
mkdir -p deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
chmod 700 deploy/shared/certs deploy/shared/certs/{etch-sso.samsungds.net,etch.samsungds.net,ca}
```

평소 사용하는 파일 전송 도구로 다음 파일을 넣습니다. 이미 배치했다면 이름과 위치만 확인합니다.

| 넣을 폴더 | 넣을 원본 파일 |
| --- | --- |
| `deploy/shared/certs/etch-sso.samsungds.net/` | `etch-sso.samsungds.net.pfx`, `etch-sso.samsungds.net.p7b` |
| `deploy/shared/certs/etch.samsungds.net/` | `etch.samsungds.net.pfx`, `etch.samsungds.net.p7b` |
| `deploy/shared/certs/ca/` | `SECDS-T2IssuingCA.crt`, `SECDS-T2RootCA.crt` |

아직 `fullchain.crt`, `private.key`, `keycloak-ca-bundle.pem`이 없어도 정상입니다.
이미 추출한 `fullchain.crt`와 `private.key`를 사용하려면 해당 사이트 폴더에 함께 넣습니다.

### 준비 C. 파일 권한 설정

원본 파일을 넣은 뒤 PFX의 읽기 권한을 소유자로 제한합니다. 추출 시 개인키 권한은 자동으로 설정됩니다.

```bash
chmod 600 deploy/shared/certs/etch-sso.samsungds.net/etch-sso.samsungds.net.pfx \
  deploy/shared/certs/etch.samsungds.net/etch.samsungds.net.pfx
```

파일은 배포 명령을 실행하는 계정이 읽을 수 있어야 합니다.
Git으로 실제 인증서가 전송되지는 않으므로 서버마다 필요한 파일은 별도로 넣습니다.

**다음:** 원본에서 새로 추출하려면 1-1 → 1-3, 기존 결과 파일을 사용하려면 1-1 → 1-4로 진행합니다.

다음은 [사이트 선택과 추출·검증](02-extract.md)입니다.
