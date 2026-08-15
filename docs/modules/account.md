# Account

Account feature는 Keycloak identity를 Django session과 업무 데이터 FK에 연결하는 shadow `User`를 소유합니다. 권한, 기본 소속과 역할의 원본은 Keycloak입니다.

## 저장 계약

shadow `User`는 다음을 저장합니다.

- 서명된 불변 식별자인 `sabun`과 Keycloak `sub`
- Knox ID, email, 표시 이름 같은 사용자 snapshot
- Keycloak affiliation parent group ID
- `/affiliations/<소속>/<viewer|member|manager>` group path
- realm/client role snapshot과 마지막 동기화 시각
- 업무 화면 필터에 사용하는 표시용 기본 소속 snapshot

authorization code callback과 access token refresh만 shadow 값을 갱신합니다. Account UI나 Django Admin에서 권한을 쓰지 않습니다. Django superuser는 접근 우회로 사용하지 않습니다.

## 접근 판정

- `portal-user/admin`이 Portal 접근의 전제입니다.
- `<scope>-user`는 해당 앱과 자기 기본 소속 데이터만 허용합니다.
- `<scope>-admin`은 해당 앱의 전체 데이터를 허용합니다.
- 기본 affiliation group 누락·중복 또는 모르는 role은 fail-closed입니다.

## UI와 API

| 구분 | 경로 |
| --- | --- |
| 화면 | `/settings/account` |
| API | 읽기 전용 `/api/v1/account/users`, `/api/v1/account/line-sdwt-options` |
| 사용자 session 정보 | `/api/v1/auth/me` |

화면은 내 정보, 기본 소속과 Keycloak 역할을 읽기 전용으로 표시합니다. 멤버·권한 관리 route와 Account 쓰기 endpoint는 제공하지 않습니다.

## Legacy cutover

전환 도구는 현재 유효한 기본 소속과 Portal·앱 user/admin만 Keycloak에 반영합니다. pending, denied, 만료 grant, 추가 데이터 범위와 상세 감사 이력은 이관하지 않습니다. legacy non-User Account 테이블은 실제 cutover의 DB backup, row count/checksum, realm export·복원 시험과 권한 비교가 완료될 때까지만 rollback 증적으로 유지합니다. 검증 뒤 별도 irreversible migration으로 제거합니다.

상세 명령과 순서는 `docs/operations.md`의 Keycloak 권한 전환 절을 따릅니다.
