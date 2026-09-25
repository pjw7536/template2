# ExecPlan: Keycloak discovery 실행 경로 재점검

## 목표
- 운영 env와 README 명령의 불일치를 재현하고 문서·실행 도구를 일치시킨다.
- deploy/keycloak 전체의 문서, 원본, 생성 파일 및 관련 테스트를 교차 점검한다.

## 현재 상태
- discovery 명령만 metadata를 해석하며 공통 env-check/k8s-env는 삭제된 endpoint를 요구한다.
- README와 k8s 안내는 기존 명령을 그대로 제시한다.
- discovery 도구는 입력 검사 오류를 일반 오류로 숨겨 누락된 키를 알기 어렵다.

## 범위
- deploy/keycloak 및 연결된 deploy/shared env 도구, 관련 테스트·문서.
- 실제 배포, 사용자·권한 변경, 자동 커밋·push는 수행하지 않는다.

## 설계
- metadata 변환을 한 구현으로 재사용하며 공통 env 도구도 discovery env를 해석한다.
- 변환된 비공개 임시 env에서는 discovery 키를 제외해 중복 조회·재귀를 방지한다.
- README는 통합 명령을 기본으로 안내하고 수동 실행 시 ConfigMap·Job 선행 조건을 명시한다.
- 값 없이 입력 키 이름을 알려주는 사전 검사와 실제 shell 진입점 회귀 테스트를 추가한다.

## 실행 단계
- [x] 실패 재현 및 폴더 파일·연동 계약 점검
- [x] discovery 해석 공통 연결 및 문서 수정
- [x] 테스트·정적 검사·렌더 비교·문서 링크 확인

## 검증
- 기존 명령으로 오류를 재현하고 discovery-only 입력으로 수정 후 통과 확인
- discovery, environment, server-checkout, SDWT, Keycloak up 테스트
- make server-check APP=keycloak PROFILE=prod, make k8s-export, shell/JSON 문법, diff 검사
- 운영 credential 및 시험 서버 부재로 실제 로그인·클러스터 적용은 제외

## 위험과 대응
- Secret 값 노출: 임시 파일을 비공개로 만들고 출력에서 원문을 숨긴다.
- 다른 앱 env 계약: Keycloak oidc+discovery 입력에만 변환을 적용한다.
- 생성 파일 불일치: 원본 렌더 결과와 추적 파일을 비교한다.

## 진행 기록
- 2026-09-25: 요청된 오류의 코드 경로와 문서 불일치를 확인했다.
- 2026-09-25: deploy/keycloak의 문서 6개, YAML 7개, env 1개, Python 3개, shell 4개, CSV 4개, JSON 3개를 대상으로 링크·문법·렌더·관련 계약을 확인했다. 생성 YAML은 원본 재렌더 결과와 동일했다.
- 2026-09-25: 기존 shell env-check/Secret 등록 경로도 discovery 해석기를 호출하도록 연결했다. URL 재입력 없이 해석된 endpoint가 Secret에 전달되고, metadata 실패 시 Secret을 쓰지 않는 회귀 테스트를 추가했다.
- 2026-09-25: discovery 13개, environment/server-checkout 53개, Keycloak up 13개, SDWT 6개 통과(총 85개). SDWT 실제 서버 통합 9개는 시험 서버 미지정으로 건너뛰었다. 서버 정적 검사, shell/JSON/YAML 문법, 문서 링크, 예시 CSV, diff 검사 통과.
- 2026-09-25: 실제 discovery에 검사용 client 문자열을 사용해 기존 check-env 경로가 통과함을 확인했다. 이 검사는 로그인이나 credential 유효성을 확인하지 않는다. 운영 Secret/Job/클러스터는 변경하지 않았다.
