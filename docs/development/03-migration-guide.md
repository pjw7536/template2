# DB migration 적용 안내

[문서 홈](../README.md) · [첫 셋업](../getting-started/01-setup.md) · [자주 쓰는 명령](../getting-started/02-usage.md)

## 적용 전 준비

서버 적용 시 DB migration을 API 시작과 분리합니다. 앱 역할과 SDWT 그룹은 Keycloak에서 관리합니다.
Account 무결성 명령은 DB 정합성을 검사합니다. 로그인 권한은 Keycloak 앱 역할·SDWT 그룹으로 관리합니다.

운영 API entrypoint는 migration을 자동 실행하지 않습니다. 신규 설치는 앱 시작 전에,
기존 환경 갱신은 API와 관련 쓰기 작업을 중지한 상태에서 같은 배포 이미지로 migration을 실행합니다.
먼저 [Portal 운영 배포](../../deploy/portal/k8s/overlays/prod/README.md)의 DB·Secret·이미지 입력을 준비합니다.
실행 명령과 검사 Job 준비 방법의 원본은 서버 checkout에 포함되는 [운영 Migration 절차](../../deploy/portal/docs/01-install.md#3-migration)입니다.

## 적용 순서

### 1. 배포 전 확인

배포 후보 이미지를 준비한 뒤 신규 DB인지 기존 DB 갱신인지 확인합니다.
신규 DB에는 `pg_trgm` extension을 먼저 준비하고, 업무 테이블이 아직 없으므로 사전 Account 무결성 검사는 생략합니다.
기존 DB는 적용할 migration의 SQL·데이터 변경·외부 작업 의존성을 검토하고 중지 대상·복원할 API replica 수를 확인합니다.

운영 migration overlay를 렌더링해 배포 후보 이미지·namespace·`api-env` Secret을 확인합니다.

```bash
kubectl kustomize deploy/portal/k8s/overlays/prod/migrate
```

검사 Job은 운영 절차의 `portal_permission_check` 함수를 사용합니다. 배포 후보 이미지·namespace·
`api-env` Secret을 재사용하고 자동 재시도 없이 실행합니다. 위 렌더 명령 자체는 DB를 변경하지 않습니다.

### 2. API 중지 후 DB migration 실행

기존 DB 갱신은 API와 DB에 쓰는 관련 worker·Airflow 작업을 중지하고, 진행 중인 쓰기가 끝난 뒤
DB 백업·migration ledger·대상 테이블 row 수를 확인합니다. 이 상태에서
`check_access_permission_integrity --phase pre-migration`을 실행하고 완료 상태와 로그를 확인합니다.
실패하면 migration을 진행하지 않습니다.

신규 DB는 위 중지·사전 검사 단계 없이 migration으로 진행합니다.
두 경우 모두 동일 후보 이미지와 Secret의 migration Job(`python manage.py migrate --noinput`)을 실행합니다.
이전 완료 Job은 결과를 보관한 뒤 해당 Job만 삭제하고 재생성합니다. 진행 중이거나 실패한 Job은 원인부터 확인합니다.

### 3. Migration 이후 무결성 확인

신규 설치와 기존 DB 갱신 모두 `portal_permission_check`로 별도 이름의 사후 검사 Job을 실행합니다.
검사 명령은 `manage.py check_access_permission_integrity --phase post-migration`이며,
동일 이미지·DB·Secret으로 실행하고 완료 상태와 로그를 확인합니다.

검사가 실패하면 API와 쓰기 작업을 시작하지 않습니다. 신규 설치는 원인을 해결한 뒤 검사하고,
기존 DB는 백업·변경분을 확인해 준비한 복구 절차를 따릅니다.

### 4. 신버전 서비스 시작과 smoke test

[운영 overlay 배포 순서](../../deploy/portal/k8s/overlays/prod/README.md)에 따라 후보 이미지를 적용하고,
기존 환경은 기록한 API replica 수를 복원하고 신규 설치는 overlay의 replica 수로 시작합니다.
rollout과 기능 검증을 완료한 뒤 중지했던 작업을 재개합니다.

일반 사용자 접근을 확인합니다. 관리자 역할이 필요하면 Keycloak Portal client의
`portal-admin` 또는 해당 앱의 관리자 역할을 명시적으로 부여하고 재로그인합니다.
DB migration으로 로그인 권한을 부여하거나 기존 사용자 권한을 일괄 변경하지 않습니다.

## 적용 후 확인

재로그인 후 `/api/v1/auth/me`의 `scopeAccess`, `sdwtAccess`가 Keycloak 역할·그룹과
일치하는지 확인합니다. 기존 DB 권한 관리 API는 `410 managed_by_keycloak`을 반환합니다.
