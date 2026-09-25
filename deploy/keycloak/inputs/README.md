# SDWT 등록 입력 템플릿

이 폴더는 운영자가 복사해 작성하는 **등록 입력 양식**을 보관합니다.

| 파일 | 작성할 내용 |
| --- | --- |
| [sdwts.template.csv](sdwts.template.csv) | SDWT 이름과 line ID |
| [users.template.csv](users.template.csv) | 사용자 EPID·소속·선택 신원 필드 |

두 파일은 헤더만 있는 빈 양식입니다. 저장소 밖 경로에 복사해 실제 값을 작성합니다.
작성한 데이터가 있는 파일을 `KEYCLOAK_SDWTS_CSV`, `KEYCLOAK_USERS_CSV`로 전달합니다.
빈 양식을 그대로 등록하지 않으며 실제 사용자 파일은 Git에 넣지 않습니다.

입력 규칙과 실행 명령은 [SDWT 최초 등록](../07_SDWT_SETUP.md)에 있습니다.
