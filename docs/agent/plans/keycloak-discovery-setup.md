# ExecPlan: Keycloak discovery 초기 설정

## 목표
- env의 discovery URL로 IdP 접속 정보를 확인하고 IdP → 프로필·mapper 설정을 순서대로 실행한다.

## 현재 상태
- IdP Job은 명시적 endpoint를 받고, 별도 claim Job이 기존 16개 claim 계약을 관리한다.
- Portal client와 token mapper는 Portal 소유 Job이 관리한다.

## 범위
- Keycloak 실행 도구, Makefile, env 입력, 운영 문서와 해당 테스트.
- 기존 계정 연결 정책과 mapper 계약은 유지한다.

## 설계
- Python 표준 라이브러리로 실행 호스트에서 discovery를 읽어 기존 Job의 env 계약으로 변환한다.
- 기존 env 검증·Secret 적용 도구를 재사용한다. 임시 입력은 비공개 디렉터리에 만들고 종료 시 제거한다.
- context를 필수 지정하며 기본은 사전 검사, apply 명령에서만 순차 Job 실행한다.
- Portal 설정은 별도 env를 명시한 경우 기존 Portal Job까지 실행한다.

## 실행 단계
- [x] discovery 입력 검증과 순차 실행 도구 추가
- [x] 실행 진입점과 운영 문서 연결
- [x] 실패 중단·metadata 검증·순서 테스트

## 검증
- Python unittest, 기존 environment 및 server-checkout 테스트
- make server-check APP=keycloak PROFILE=prod
- git diff --check

## 위험과 대응
- discovery만으로 credential·claim 의미는 알 수 없다. 발급 정보와 기존 claim 계약을 사용한다.
- 호스트에서 사내 endpoint에 접근할 수 없으면 실패한다. TLS 검증을 끄지 않으며 실제 로그인 검증은 운영망에서 수행한다.
- Job은 트랜잭션이 아니다. 실패한 단계에서 중단하고 수정 후 재실행한다.

## 진행 기록
- 2026-09-25: 사용자가 확인한 request body 방식에 맞춰 인증 방식을 client_secret_post로 고정하고, 운영 env의 discovery 파생 URL·issuer 6개 입력을 제거한다. 문서에 discovery 명령 사용을 명확히 하고 기존 테스트와 실제 사전 검사를 수행한다.
- 2026-09-25: 정리 후 discovery 테스트 8개·서버 정적 검사·diff 검사가 통과했다. 실제 discovery 해석과 인증 방식 검증은 통과했으나 env의 client ID·secret이 비어 있어 후속 입력 검사에서 중단됐다. 클러스터 적용은 수행하지 않았다.
- 2026-09-25: 기존 Job을 재사용하는 실행 호스트 기반 discovery 흐름으로 설계했다.
- 2026-09-25: 신규 unittest 8개, 기존 environment/server-checkout 53개 및 Keycloak server-check가 통과했다.
- 2026-09-25: 제공된 discovery URL 조회 성공. issuer와 code/openid 지원, basic/post 지원을 확인했다. 현재 env의 client 인증 방식이 비어 있어 실제 사전 검사는 실패했고 클러스터에는 적용하지 않았다. 사내 사용자 claim의 실제 발급·로그인은 운영 시험 계정으로 확인해야 한다.
