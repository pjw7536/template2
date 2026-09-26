# ExecPlan: 운영 Ingress 명칭 통일

## 목표
- Keycloak과 Headlamp의 namespace·Ingress 이름·host·TLS Secret을 사용자 지정값으로 안내한다.
- Airflow HTTPS 가이드에서 업무 도메인의 인증서 원본을 명확히 한다.

## 현재 상태
- Keycloak manifest와 Headlamp env는 이미 지정값과 일치한다.
- Headlamp 환경변수 문서는 예시 도메인을 사용하고 Airflow TLS 복사 예시는 Keycloak 도메인 또는 임의 입력을 안내한다.

## 범위
- deploy의 관련 설치·TLS·Ingress·Airflow 문서와 실행 계획.
- 실행 코드·로컬 개발 설정·기존 비밀값·라이브 클러스터는 변경하지 않는다.

## 설계
- 공용 Ingress 안내에 두 앱의 기준 표를 두고 각 앱 가이드에서 참조한다.
- Keycloak: etch-sso / keycloak / etch-sso.samsungds.net / keycloak-tls.
- Headlamp: headlamp / headlamp / etch.samsungds.net / headlamp-tls.
- Airflow는 https://etch.samsungds.net/airflow 및 airflow/airflow-tls를 유지하고 headlamp/headlamp-tls에서 최초 복사한다.
- API·DB·auth 코드 계약 변경 없음. 운영 env 입력 예시만 구체화한다.

## 실행 단계
- [x] 설정과 문서의 기존 값 확인
- [x] 관련 가이드 통일
- [x] 정적 검사와 문서 차이 검토

## 검증
- make server-check APP=keycloak PROFILE=prod
- make server-check APP=headlamp PROFILE=prod
- make server-check APP=airflow PROFILE=prod
- git diff --check 및 변경 문서 링크·설정값 대조

## 위험과 대응
- 위험: 다른 도메인의 인증서를 복사하거나 namespace 간 Secret을 직접 참조할 수 있다고 오해할 수 있다.
- 대응: 원본 headlamp/headlamp-tls와 대상 airflow/airflow-tls를 구분하고 자동 갱신되지 않음을 안내한다.

## 진행 기록
- 2026-09-26: 사용자 지정값에 맞춰 공용 기준 표, 앱별 설정·TLS 가이드, Airflow 인증서 복사 및 SSO URL 예시를 통일했다.
- 검증: Keycloak server-check 통과. Headlamp·Airflow server-check는 로컬 Helm 실행 파일 부재로 실행 불가. git diff --check와 변경 문서의 상대 파일 링크 검사 통과. 라이브 클러스터에는 적용하지 않았다.
