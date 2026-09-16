# ExecPlan: 앱 소유 환경설정과 Keycloak 설정 작업 분리

## 목표

- 환경변수 원본을 앱별 `env/portal`, `env/keycloak`, `env/airflow`, `env/monitoring`에 모은다.
- 기존 profile 값과 로컬 외부계 동작을 유지하면서 중복 주입을 줄인다.
- Keycloak 기동, 사내 OIDC 설정, Portal client 등록을 독립 실행한다.
- 설정값을 노출하지 않는 필수값 검사와 운영 안내를 제공한다.

## 현재 상태

- Portal API는 profile별 146개 이상의 key를 가지며 로컬 K8s는 파일/override/YAML로 중복 설정한다.
- 기존 Keycloak runtime 파일의 Portal client와 주소는 realm 초기 import가 요구한다.
- Nginx 본체는 API Secret을 받지 않는다. Django collectstatic 초기 컨테이너만 사용하므로 해당 구조는 유지한다.
- 기존 Compose와 관련 앱 소스에 미커밋 변경이 있다.

## 범위

- 환경설정 경로, 배포 wiring, 설정 검사, Keycloak 관리 스크립트와 문서를 변경한다.
- Django 업무 로직, 기존 env key 이름과 인증 프로토콜은 바꾸지 않는다.
- 실제 클러스터 적용, 운영 credential 교체, commit/push는 하지 않는다.

## 설계

- Portal profile의 api/web/minio는 `env/portal/<profile>`, Airflow와 monitoring은 앱별 profile 파일로 이동한다.
- 실제 Keycloak 값은 Git 제외 `env/keycloak/prod.env`로 이동하고 기존 Secret key 이름을 보존한다.
- Portal client 값은 Portal internal API 설정에서 관리하고 Keycloak은 빈 etch realm만 초기 import한다.
- 로컬 K8s는 기본 local API 설정과 한 개의 명시적 K8s 차이 파일을 합쳐 하나의 API Secret을 만든다. Pod YAML의 중복 env는 제거한다.
- keycloak 서버, oidc 연결, portal client 작업별 필수 key만 검사하며 기존 설정 작업은 명시적으로 실행한다.
- 외부계 URL과 보안 옵션은 env로 전달하고 Secret 전체를 다른 서버에 주입하지 않는다.

## 실행 단계

- [x] 기준 Compose/Kustomize 설정과 env key/value 보존 증거를 확보한다.
- [x] 앱별 env 이동과 소비자·검사 스크립트 참조를 수정한다.
- [x] 로컬 K8s 중복 설정을 제거한다.
- [x] Keycloak 기동과 oidc/client 설정 작업을 분리한다.
- [x] 누락·중복·placeholder 검사와 실패 경로 테스트를 추가한다.
- [x] 문서, 예시, 생성 YAML과 검증 결과를 갱신한다.

## 검증

- 이동 전후 Compose 병합 설정, 기존 env 값과 로컬 K8s 유효 설정을 비교한다.
- 설정 검사 성공/누락/placeholder/중복 및 secret 비노출을 모의검증한다.
- Keycloak 관리 작업의 create/update, 기존 realm 비파괴와 작업별 입력 분리를 모의검증한다.
- `make env-profile-key-check`, `make k8s-render`, `make k8s-export`, Compose config 검사, Shell 문법, 문서 감사와 `git diff --check`.

## 위험과 대응

- 위험: 관리 화면의 기존 Keycloak 설정이 초기 import 변경으로 유실될 수 있다.
- 대응: realm 삭제/재생성 없이 기존 realm을 유지하고 관리 작업은 별도 실행하도록 한다.
- 위험: env 이동·합성 중 credential이 출력되거나 Git 대상이 될 수 있다.
- 대응: 값은 로그에 출력하지 않고 Git 제외·권한을 먼저 설정하며 기존 값을 보존한다.
- 위험: 로컬 Compose의 ADFS와 K8s의 Keycloak 차이가 없어질 수 있다.
- 대응: 명시적 K8s 차이 파일을 한 번만 적용하고 유효 설정을 비교한다.

## 진행 기록

- 2026-09-11: 사용자가 앱별 env 정리, 중복 제거, Keycloak 설정 단계 분리와 필수값 검사를 승인했다.
- 2026-09-11: 기존 env 16개는 내용 동일성을 확인했으며 Compose dev/oidc/prod/test 병합 결과도 동일했다. 로컬 K8s API는 최종 key/value 비교로 기존 값을 유지했다.
- 2026-09-11: Keycloak 기동 입력을 4개로 줄이고 Portal credential을 Git 제외 `env/portal/internal/api.env`로 보존했다. internal의 Portal DNS와 DB는 실제 배포 전 입력해야 한다.
- 2026-09-11: 기존 사내 OIDC 연결값은 클러스터에 있어 임의로 복사하지 않았다. env에서 재설정할 경우 `CORP_OIDC_*`를 작성하고 명시적으로 Job을 실행해야 한다.
- 2026-09-11: env 및 관리 작업 회귀 테스트 15개, agent 테스트 12개, Compose 검사, Kustomize/render, 문서 감사와 Shell 문법 검사를 통과했다. 실제 사내 클러스터와 로그인 검증은 수행하지 않았다.
