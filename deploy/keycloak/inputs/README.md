# SDWT 등록 입력 템플릿

이 폴더는 SDWT 그룹·사용자 등록에 쓰는 CSV의 **입력 양식**을 보관합니다.

| 파일 | 작성할 내용 |
| --- | --- |
| [sdwts.template.csv](sdwts.template.csv) | SDWT 이름, 라인(line_id), 팀(department, 사내 부서명과 같은 값) |
| [users.template.csv](users.template.csv) | 사용자 EPID·소속·선택 신원 필드 |

두 파일은 헤더만 있는 빈 양식입니다. 저장소 안의 양식은 고치지 않고, 요청으로 받은 소속 데이터를 같은 헤더로 저장소 밖 경로에 작성합니다.
작성한 데이터가 있는 파일의 절대 경로를 `KEYCLOAK_SDWTS_CSV`, `KEYCLOAK_USERS_CSV`로 전달합니다.
빈 양식을 그대로 등록하지 않으며 실제 사용자 파일은 Git에 넣지 않습니다.

입력 규칙과 작성 위치는 [입력 파일 검사](../docs/02-configure.md#1-입력-파일-검사), 실행 순서는 [Keycloak 가이드의 선택 절](../README.md#선택-sdwt-소속역할-관리-api)에 있습니다.
