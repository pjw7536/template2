# 앱 역할 카탈로그

`catalog.json`은 Keycloak 앱 client의 역할, 포함 관계, 기본 역할과 권한관리 웹 매트릭스 열의 원본입니다.
`make keycloak-access-apply`가 이 파일을 Keycloak에 반영합니다. 기본은 계획만 출력하는 dry-run이고 `KEYCLOAK_ACCESS_APPLY=1`을 붙이면 적용합니다.

항목 형식·실행 절차는 [앱 역할](../docs/02-configure.md#앱-역할), 실행 순서는 [Keycloak 가이드의 선택 절](../README.md#선택-sdwt-소속역할-관리-api), 앱의 판단 규칙은 [권한관리 웹 문서](../../../apps/iam/README.md#권한-모델)에 있습니다.
