# Migration Guide

## 목적

서버 적용 시 DB migration을 API 시작과 분리하고, 권한 관리자는 지정한 Django
superuser가 필요한 사용자에게 명시적으로 부여한다.

운영 API entrypoint는 migration을 자동 실행하지 않는다. 운영자가 API를 중지한 상태에서
같은 release image로 migration과 무결성 검사를 명시적으로 실행한다.

## 적용 순서

### 1. 배포 전 확인

배포 후보 image를 준비한 뒤 운영 DB의 migration ledger, 대상 테이블 row 수와 백업을
확인한다. 다음 검사는 DB를 변경하지 않는다.

```bash
docker compose -f docker-compose.yml run --rm --no-deps --entrypoint python api \
  manage.py check_access_permission_integrity --phase pre-migration
```

검사가 실패하면 migration을 실행하지 않는다.

### 2. API 중지 후 DB migration 실행

구버전 API와 권한 관련 worker를 모두 중지한 뒤 migration을 한 번만 실행한다.

```bash
docker compose -f docker-compose.yml stop api
docker compose -f docker-compose.yml run --rm --no-deps --entrypoint python api \
  manage.py migrate --noinput
```

### 3. Migration 이후 무결성 확인

```bash
docker compose -f docker-compose.yml run --rm --no-deps --entrypoint python api \
  manage.py check_access_permission_integrity --phase post-migration
```

검사가 실패하면 API를 시작하지 않고 DB 백업 복원 절차를 따른다.

`account 0005`는 저장소 내부 소비처가 없는 `account_user_profile` 테이블을 제거합니다.
운영 DB를 직접 조회하는 외부 작업이 이 테이블을 사용하지 않는지 migration 전에 확인합니다.

### 4. 신버전 서비스 시작과 smoke test

```bash
docker compose -f docker-compose.yml up -d api web nginx
```

일반 사용자 접근을 확인한다. Portal 또는 앱 관리자가 필요하면 사전에 지정한 Django
superuser로 권한 관리 화면에 접근해 대상 사용자에게 `admin` 역할을 명시적으로 부여한
뒤 다시 확인한다. 배포 과정에서 일반 사용자 권한을 일괄 생성하거나 덮어쓰지 않는다.

## 적용 후 확인

권한 관리 화면에서 명시적으로 변경한 사용자별 `portal`, 앱 scope의 상태와 역할이
예상과 일치하고 감사 로그가 생성됐는지 확인한다.
