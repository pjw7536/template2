# ExecPlan: 배포 검토 후속 정정

## 목표
- Airflow는 기존 DB를 이전하지 않고 새 DB로 설치하는 기준을 명확히 한다.
- 나머지 검토 항목인 Worker 안내 충돌, Portal 설정 반영, env 예외, MinIO 이미지 고정과 문서 가독성을 수정한다.

## 현재 상태
- deploy에는 기존 사용자 변경이 있으므로 현재 작업 내용을 보존한다.
- 최신 현황은 khplane01w09를 Keycloak 전용으로 지정하지만 과거 통합 실행은 Airflow도 같은 노드를 요구한다.
- Portal Secret 등록 후 재시작 명령이 빠져 있고 MinIO와 mc 이미지는 latest다.

## 범위
- deploy의 관련 Markdown과 MinIO 기본 manifest를 수정한다.
- DB 이전 절차의 기능 수정, 실제 노드·credential 결정, 클러스터 배포·삭제, commit·push는 수행하지 않는다.

## 설계
- 신규 Airflow 설치는 앱별 airflow-check/up을 기본으로 하고 통합 server-up은 과거 동일 노드 구성으로 한정한다.
- 새 DB 설치 조건과 과거 DB 이전 참고를 구분하며 실제 env의 NODE_NAME은 사용자 확인값으로 남긴다.
- Portal 설정별 Secret 등록·재시작·확인 순서를 연결한다.
- MinIO 공식 릴리스·registry manifest를 확인해 서버·mc를 고정하고 반입 목록을 문서화한다.
- 공통 env 규칙에 Headlamp·Monitoring·FTP 예외를 명시하고 인증서 문서에 작업별 바로가기를 추가한다.
- API·DB schema·auth·env 키 계약과 공개 import는 변경하지 않는다.

## 실행 단계
- [x] Airflow 신규 설치·배치·과거 통합 절차 구분
- [x] Portal 설정 반영과 공통 문서 개선
- [x] MinIO 이미지 고정·반입 안내 갱신
- [x] 렌더·회귀·문서 검증과 변경 범위 확인

## 검증
- deploy Markdown 상대 링크·제목 앵커·Shell 코드 블록 구문 검사.
- PATH에 저장소 .tools/bin을 추가해 make server-check APP=all PROFILE=prod 실행.
- Portal 배포·라우팅·서버 checkout Node 테스트와 관련 Python 배포 테스트.
- make audit-docs 및 이번 작업 차이의 공백 검사.

## 위험과 대응
- Worker를 추정해 배치하지 않고 전용 노드 제외와 확인 순서만 안내한다.
- 기존 DB·Secret·PV 삭제 절차는 추가하지 않는다.
- 고정 이미지는 registry에서 확인하되 실제 사내 pull·서버 호환성은 배포 후 검증과 구분한다.

## 진행 기록
- 2026-10-28: 사용자 지시에 따라 DB 이전 결함 수정은 제외하고 나머지 검토 결과를 수정한다.
- 2026-10-28: 공식 MinIO·mc 릴리스 존재를 확인해 각각 RELEASE.2025-09-07T16-13-09Z, RELEASE.2025-08-13T08-35-41Z로 고정했다. Docker Hub·Quay 익명 manifest 조회는 인증 오류로 완료하지 못했으므로 digest·실제 pull 성공을 주장하지 않는다. 반입 이미지 주소·고유 태그/digest 및 Worker 기동 확인을 문서화했다.
- 2026-10-28: Airflow 신규 DB 기준과 Keycloak 전용 Worker 제외를 안내하고, 동일 Worker를 요구하는 기존 server-up은 과거 호환 경로로 한정했다. 기존 DB 이전 참고와 실행 코드는 변경하지 않았다.
- 2026-10-28: Portal env별 Secret 등록·재시작·동작 확인과 공개 설정 문구를 보완했다. 공통 env 예외·Headlamp/FTP 실행 요약·인증서 작업별 바로가기를 정리했다.
- 2026-10-28: .tools/bin의 Helm을 PATH에 추가해 6개 앱 server-check와 Python 115개, Node 29개 테스트를 모두 통과했다. 운영·로컬 Portal 렌더에서 고정 이미지가 적용되는지 확인했다.
- 2026-10-28: deploy Markdown 60개의 상대 링크·제목 앵커와 Bash 코드 블록 219개, MinIO YAML 구문, make audit-docs, git diff --check를 통과했다. 실제 서버 변경·이미지 pull·로그인은 수행하지 않았다.
