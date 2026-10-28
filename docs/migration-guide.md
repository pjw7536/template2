# Migration Guide

## 목적

서버 적용 시 DB migration을 API 시작과 분리한다. 앱 역할과 SDWT 그룹은 Keycloak에서 관리한다.
아래 DB 무결성 검사는 기존 Account 테이블의 migration 점검이며 로그인 권한 부여 절차가 아니다.

운영 API entrypoint는 migration을 자동 실행하지 않는다. 운영자가 API를 중지한 상태에서
같은 release image로 migration과 무결성 검사를 명시적으로 실행한다.

## 적용 순서

### 1. 배포 전 확인

배포 후보 image를 준비한 뒤 운영 DB의 migration ledger, 대상 테이블 row 수와 백업을
확인한다. 다음 검사는 DB를 변경하지 않는다.

운영 migration overlay를 렌더링해 배포 후보 이미지·namespace·`api-env` Secret을 확인합니다.

```bash
kubectl kustomize deploy/portal/k8s/overlays/prod/migrate
```

이 Job을 기준으로 별도 이름의 사전 검사 Job을 준비합니다. 컨테이너 command는 `python`,
args는 `manage.py check_access_permission_integrity --phase pre-migration`으로 지정합니다.
검사 Job의 `backoffLimit`은 0으로 지정합니다. 대상 context를 명시해 실행하고 Job 완료 상태와 로그를 확인합니다.

검사가 실패하면 migration을 실행하지 않는다.

### 2. API 중지 후 DB migration 실행

구버전 API와 권한 관련 worker를 모두 중지한 뒤 migration을 한 번만 실행한다.

대상 context·namespace와 기존 API replica 수를 기록하고 API를 0으로 축소합니다.
Airflow 등에서 API를 호출하는 권한 관련 작업도 중지합니다. 동일 후보 이미지와 Secret을 쓰는
migration Job(`python manage.py migrate --noinput`)을 한 번 실행하고 완료 상태와 로그를 확인합니다.
이전 실행 Job이 남아 있다면 결과를 보관한 뒤 새 실행 이름을 사용합니다.

### 3. Migration 이후 무결성 확인

같은 Job 원본에서 별도 이름의 사후 검사 Job을 준비하고 args를
`manage.py check_access_permission_integrity --phase post-migration`으로 지정합니다.
동일 이미지·DB·Secret으로 실행하고 완료 상태와 로그를 확인합니다.

검사가 실패하면 API를 시작하지 않고 DB 백업 복원 절차를 따른다.

`account 0005`는 저장소 내부 소비처가 없는 `account_user_profile` 테이블을 제거합니다.
운영 DB를 직접 조회하는 외부 작업이 이 테이블을 사용하지 않는지 migration 전에 확인합니다.

### 4. 신버전 서비스 시작과 smoke test

[운영 overlay 배포 순서](../deploy/portal/k8s/overlays/prod/README.md)에 따라 후보 이미지를 적용하고,
API replica 수를 복원해 rollout 완료를 확인합니다. 중지했던 작업은 검증 후 재개합니다.

일반 사용자 접근을 확인한다. 관리자 역할이 필요하면 Keycloak Portal client의
`portal-admin` 또는 해당 앱의 관리자 역할을 명시적으로 부여하고 재로그인한다.
DB migration으로 로그인 권한을 부여하거나 기존 사용자 권한을 일괄 변경하지 않는다.

## 적용 후 확인

재로그인 후 `/api/v1/auth/me`의 `scopeAccess`, `sdwtAccess`가 Keycloak 역할·그룹과
일치하는지 확인한다. 기존 DB 권한 관리 API는 `410 managed_by_keycloak`을 반환한다.
