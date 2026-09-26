# 00. Headlamp 최초 설치 안내

현재 Keycloak의 `etch` realm과 사내 IdP `oidc`로 로그인하는 Kubernetes 운영 UI입니다.
**Keycloak 자체 설정과 Account Console 사내 로그인 확인을 마친 뒤** 아래 순서로 설치합니다.

## 처음 시작하거나 초기화 후 다시 설치한다면

**먼저 [01 서버 준비](01_SERVER_SETUP.md)를 열고, 번호 순서대로 한 블록씩 실행하세요.**
이 README는 순서를 설명하는 입구입니다. 여러 문서의 명령을 한꺼번에 붙여 넣지 않습니다.
`01 → 03 → 04 → 05 → 06`이 실행 순서이며, `02`는 설정값을 찾을 때 여는 참고 문서입니다.

작업할 곳은 세 군데입니다.

| 작업할 곳 | 여기서 하는 일 |
| --- | --- |
| CP1의 Bash 터미널 | 저장소 루트에서 `make`·`kubectl` 실행, 인증서와 Secret 등록 |
| PC의 웹 브라우저 | Keycloak 관리자 화면에서 client·그룹 등록, 마지막에 Headlamp 로그인 |
| 각 제어면 서버의 터미널 | Kubernetes API server가 Keycloak 토큰을 받아들이도록 설정. 05에서만 사용 |

`kubectl --context ...`는 선택한 클러스터에 명령을 보냅니다. 반면 `sudo vi /etc/kubernetes/...`는
**현재 SSH로 접속한 서버의 파일**을 편집합니다. context를 바꿔도 SSH 접속 서버는 바뀌지 않습니다.

초기화 후에는 다음 상태에서 시작하면 됩니다.

- Keycloak의 `etch` realm·사내 IdP `oidc`·기존 사용자는 유지하고, Account Console 사내 로그인이 됩니다.
- `headlamp` namespace가 없어도 됩니다. 01에서 만들고, 삭제된 이미지 인증·TLS·OIDC Secret과 CA ConfigMap은 다시 등록합니다.
- Keycloak의 Headlamp client·관리자 그룹이 없어도 됩니다. 04에서 새로 만듭니다. 남아 있다면 해당 단계에서 확인합니다.
- API server의 OIDC 설정은 남아 있을 수 있습니다. 05에서 먼저 확인하고 중복 추가하거나 다른 앱의 인증 설정을 덮어쓰지 않습니다.
- 인증서 원본·개인키·CA 파일은 준비되어 있어야 합니다. namespace를 삭제했다면 Kubernetes Secret도 없어졌으므로 파일로 다시 등록해야 합니다.

문서의 `read ...` 명령은 실행 후 값을 입력하고 Enter를 누릅니다. `Headlamp client secret:` 입력은 화면에 보이지 않습니다.
`<...>` 형태의 설명용 값은 실제 값으로 바꿔야 하며 그대로 실행하지 않습니다.
오류가 나오면 해당 단계의 확인 방법으로 해결한 뒤 진행합니다. 새 터미널을 열었다면 01의 실행 입력을 다시 준비합니다.

## 설치 순서

| 순서 | 할 일 | 실행 안내 | 완료 기준 |
| --- | --- | --- | --- |
| 1 | 도구·context·env·chart·namespace 준비 | [01 서버 준비](01_SERVER_SETUP.md) | 입력·chart 검사와 이미지 인증 준비 |
| 2 | 사이트 인증서·Keycloak CA 등록 | [03 TLS](03_TLS.md) | TLS Secret·CA ConfigMap·OIDC 연결 검사 정상 |
| 3 | Headlamp client·그룹·Client secret 등록 | [04 Keycloak 설정](04_KEYCLOAK_SETUP.md) | S256·groups mapper·관리자 가입·Secret 완료 |
| 4 | 모든 API server의 OIDC 인증 설정 | [05 API server](05_APISERVER_SETUP.md) | 인증 계약 반영, 기존 관리자 접속 정상 |
| 5 | Headlamp 배포·브라우저 로그인·권한 검증 | [06 배포와 검증](06_DEPLOY_VERIFY.md) | 관리자 허용·비관리자 거부·갱신 확인 |

명령은 각 단계의 실행 안내에서만 수행합니다. `02`는 필요할 때 읽는 변수 참고 문서입니다.
같은 Bash 터미널에서 진행하고, 새 터미널이면 [01의 실행 입력](01_SERVER_SETUP.md#2-대상-context와-실행-입력)을 다시 준비합니다.
각 문서 끝의 완료 기준을 통과한 뒤 다음으로 이동합니다.

API server 설정은 필수입니다. 제어면을 직접 관리하지 않는다면 05를 담당자에게 전달하고 완료 확인을 받습니다.
Keycloak client 등록이나 Headlamp Pod Ready만으로 전체 설정이 끝나지는 않습니다.

## 로그인과 권한

```text
Headlamp → Keycloak etch → 사내 IdP oidc → Keycloak ID Token
         → Kubernetes API server 인증 → 그룹별 RBAC
```

허용한 사람만 Keycloak 최상위 `headlamp-admins` 그룹에 가입시킵니다.
Kubernetes의 `headlamp:/headlamp-admins` 그룹에 `cluster-admin`을 연결하므로
모든 namespace의 조회·수정·삭제, Secret 접근과 RBAC 관리가 가능합니다. 다른 RBAC 권한은 합산됩니다.
Headlamp Pod 자체에는 사용자 조회·관리 권한을 부여하지 않습니다.
Portal client나 SDWT 업무 그룹은 Headlamp의 client·관리자 그룹을 대신하지 않습니다.

## 참고와 운영

| 문서 | 용도 |
| --- | --- |
| [02 환경변수](env/02_ENVIRONMENT.md) | 변수 의미·외부 env·검사 범위 |
| [운영 참고](operations/README.md) | 장애 진단·Secret/CA 갱신·기존 조회 그룹 전환·복구 |
| [Keycloak 자체 설정](../keycloak/04_SETUP_FLOW.md) | 사내 로그인·기존 사용자 연결 |
| [Keycloak 사용자 필드](../keycloak/06_CLAIMS.md) | EPID·loginid·표시 이름 계약 |

`OIDC.md`와 `HTTPS_CERTIFICATE_GUIDE.md`의 절차는 03~06과 운영 참고에 통합했습니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
