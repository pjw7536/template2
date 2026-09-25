# 00. Keycloak 시작 안내

이 폴더는 사내 로그인과 업무 앱 사이에서 인증을 중개하는 Keycloak의 설치·설정·운영을 관리합니다.
서버는 Kubernetes의 `etch-sso` namespace, 업무 설정은 `etch` realm, 사내 IdP alias는 `oidc`를 사용합니다.

## 지금 필요한 작업부터 선택하세요

| 현재 상태 | 다음 작업 | 문서 |
| --- | --- | --- |
| Keycloak 서버가 아직 없음 | env·인증서·디스크 준비 후 서버 설치 | [서버 설치](01_SERVER_SETUP.md) |
| 서버만 실행 중 | Realm부터 0~5단계 순서로 설정 | [단계별 설정](04_SETUP_FLOW.md) |
| 사내 provider 로그인까지 정상 | 2번 User Profile → 3번 mapper → 4번 앱 연결 | [단계별 설정](04_SETUP_FLOW.md) |
| 로그인은 되지만 사용자 정보가 비어 있음 | 수신 claim·사용자 필드·발급 mapper 구분해서 확인 | [매핑 참고](06_CLAIMS.md) |
| 인증서 만료·신뢰 오류 | 공개 사이트 인증서와 접속 주체의 CA 신뢰 확인 | [TLS 운영](03_TLS.md) |
| 사용자 소속·SDWT 접근 권한 등록 | CSV 검사 → dry-run → 적용 | [SDWT 설정](07_SDWT_SETUP.md) |

## 전체 흐름

```text
서버 설치
  → 0. Realm 생성
  → 1. Identity Provider 연결
  → 2. User Profile 등록
  → 3. IdP mapper 설정
  → 4. Portal client·token mapper 설정
  → 5. 소속·SDWT 그룹 권한 설정 (선택)
  → 시험 계정으로 사내 재로그인·앱 확인
```

기본 실행 방식은 **한 단계씩**입니다. [04_SETUP_FLOW.md](04_SETUP_FLOW.md)에 각 단계의 실행 파일,
Make 명령, 입력, 완료 확인을 모았습니다. 이미 끝난 단계는 다시 실행하지 않아도 됩니다.

## 용어와 역할

| 용어 | 이 프로젝트에서 하는 일 |
| --- | --- |
| Realm | 사용자·client·로그인 설정을 묶는 영역. 대상은 `etch` |
| Identity Provider (IdP) | 사내 AD FS에 로그인을 위임하는 연결. alias는 `oidc` |
| Discovery | 사내 OIDC의 Authorization·Token·JWKS 등 접속 정보를 조회하는 metadata |
| User Profile | 사용자 필드 이름과 조회·편집 정책 |
| IdP mapper | 사내 로그인 응답의 claim을 Keycloak 사용자 필드에 저장하는 규칙 |
| Client | Keycloak 로그인을 사용하는 앱. 예: Portal |
| Token mapper | 사용자 필드를 앱에 전달할 토큰 claim으로 변환하는 규칙 |
| SDWT 그룹 | 소속과 별도로 앱 접근 등급을 나타내는 그룹 |

**사내 IdP용 client ID·secret과 Portal용 client ID·secret은 서로 다른 입력입니다.**
어디에 넣을지는 [환경변수 안내](env/02_ENVIRONMENT.md)에서 확인하세요.

## 앱에 전달하는 claim 이름

현재 token mapper는 `loginid → loginid → loginid`처럼 **사내 claim 이름으로 반환**합니다.
가운데는 Keycloak 내부 저장 이름입니다. Portal DB의 `knox_id`와 반환 claim `loginid`를 구분합니다.
현재 등록 경로는 Portal client 대상이며 다른 앱에는 mapper 설정과 연결 검증이 별도로 필요합니다.
전체 매핑과 적용 범위는 [매핑 참고](06_CLAIMS.md)에 있습니다.
기존 사용자에 이전 속성값이 있다면 [저장 이름 전환](06_CLAIMS.md#기존-사용자-저장-이름-전환)을 따라 2번 프로필 등록과 3번 mapper 사이에 값을 복사합니다.

## 문서 지도

문서 번호는 읽는 순서이며, 실행 파일의 0~5단계 번호와는 별개입니다.

| 번호 | 문서 | 읽는 목적 |
| --- | --- | --- |
| 00 | README (현재 문서) | 상황별 시작점·용어·전체 흐름 |
| 01 | [서버 설치](01_SERVER_SETUP.md) | 서버 준비·기동 검사·수동 YAML 배포 참고 |
| 02 | [환경변수](env/02_ENVIRONMENT.md) | 단계별 입력 파일·환경변수·Secret 구분 |
| 03 | [TLS](03_TLS.md) | 사이트 인증서 적용과 CA 신뢰 문제 해결 |
| 04 | [단계별 설정](04_SETUP_FLOW.md) | Realm부터 0~5단계 독립 실행 |
| 05 | [Discovery](05_DISCOVERY_SETUP.md) | 사내 입력 해석과 기존 통합 실행 방식 |
| 06 | [매핑 참고](06_CLAIMS.md) | EPID·사용자 필드·수신/발급 mapper 계약 |
| 07 | [SDWT 설정](07_SDWT_SETUP.md) | CSV·관리자 인증·소속·그룹 초기 설정 |
| 08 | [Kubernetes 원본](k8s/08_KUBERNETES.md) | manifest·Job·생성 파일 유지보수 |

## 실행 전 알아둘 점

- 명령은 저장소 루트의 Bash에서 실행합니다. 서버 실행에는 `Makefile`, `deploy/keycloak`, 필요한 `deploy/shared`가 있어야 합니다. [서버 선택 checkout](../SERVER_CHECKOUT.md)을 사용합니다.
- `KUBE_CONTEXT`를 받는 명령에는 대상 context를 명시합니다. 설정 파일을 고치는 것만으로 서버가 바뀌지는 않습니다.
- 단계별 0~4번은 Kubernetes Job, 5번 SDWT는 관리자 API와 CSV를 사용합니다.
- 정적 검사나 Job 완료는 실제 로그인 검증과 다릅니다. 마지막에 시험 계정으로 사용자 정보와 앱 로그인을 확인합니다.
- 최초 설치·일반 재적용은 기존 DB/PVC를 삭제하지 않습니다. 빈 DB 재설치는 [별도 운영 절차](../shared/docs/operations/keycloak-fresh-start.md)입니다.

## 기존 안내에서 찾아온 경우

### 6. 사내 OIDC client 발급

발급 정보와 discovery 입력은 [Discovery 안내](05_DISCOVERY_SETUP.md), 실제 독립 실행은
[1번 Identity Provider](04_SETUP_FLOW.md#1-identity-provider-생성)를 따릅니다.

### 7. 사내 OIDC 사용자 claim 일괄 매핑

필드별 설명은 [매핑 참고](06_CLAIMS.md)로 옮겼습니다. 신규 실행은
[2번 User Profile](04_SETUP_FLOW.md#2-user-profile-등록)과 [3번 IdP mapper](04_SETUP_FLOW.md#3-idp-mapper-설정)를 나누어 수행합니다.

### 8. Portal API 연결

[4번 Portal client·token mapper](04_SETUP_FLOW.md#4-portal-clienttoken-mapper-설정)와
[Portal 소유 client 계약](../portal/k8s/jobs/keycloak-client/README.md)을 따릅니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
