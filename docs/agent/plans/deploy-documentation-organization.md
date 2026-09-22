# ExecPlan: 배포 문서 목적별 정리

## 목표
- deploy 문서를 설정·운영·인프라·앱별 배포 목적에 맞게 배치하고 진입 문서에서 안내한다.

## 현재 상태
- 공통 ENVIRONMENT, SERVER_START, CP1 문서가 deploy 루트에 흩어져 있다.
- 공통 클러스터 현황이 Portal prod overlay 문서에 포함되어 있다.
- 작업 폴더에 기존 staged/unstaged 변경이 있으며 그 내용을 보존한다.

## 범위
- deploy Markdown과 이동된 문서를 참조하는 현재 안내 문서의 링크.
- 배포 코드·설정·Git index와 과거 ExecPlan 기록은 변경하지 않는다.

## 설계
- 공통 문서는 선택 체크아웃에 항상 포함되는 deploy/shared/docs의 configuration, operations, infrastructure에 둔다.
- deploy/README.md는 목적별 문서 색인, SERVER_CHECKOUT.md는 기존 공통 진입 경로로 유지한다.
- 앱별 README와 리소스 옆 문서는 해당 앱의 상세 절차를 소유한다.
- Portal 문서의 공통 현황을 infrastructure/cluster.md로 분리하고 Portal 준비 항목은 유지한다.
- API/DB/auth/env 계약 변경은 없다.

## 실행 단계
- [x] 문서와 참조 경로, 선택 체크아웃 범위 확인
- [x] 공통 문서 이동과 클러스터 현황 분리
- [x] 목적별 색인·상호 링크·폴더 구조 설명 정리
- [x] 문서 링크·기존 본문 보존·diff 검증

## 검증
- 임시 Python 검사로 deploy Markdown 및 수정된 현재 문서의 상대 링크 대상 존재 확인.
- 이동 문서와 클러스터 현황의 본문·실행 코드 블록 보존 확인.
- bash scripts/agent/check_docs_inventory.sh
- git diff --check 및 작업 전후 변경 파일 범위 확인.

## 위험과 대응
- 위험: 문서 이동으로 상대 링크나 선택 체크아웃 접근이 끊길 수 있다.
- 대응: 이동 전후 경로로 링크를 재계산하고 공통 문서를 deploy/shared 안에 유지한다.
- 위험: 기존 작업 변경을 덮어쓸 수 있다.
- 대응: 현재 파일 내용을 기준으로 이동하고 문서 외 파일과 index는 건드리지 않는다.

## 진행 기록
- 2026-09-15: 요청 범위와 분류를 확정하고 문서 정리를 시작했다.
- 2026-09-15: 공통 문서 3개 이동, 클러스터 현황 분리, 목적별 색인과 상위 탐색 링크를 완료했다. 상대 링크 105개, 기존 문서 실행 코드 블록 보존, 클러스터 본문 보존, deploy 전체 문서 색인 등록, 문서 색인 스크립트와 git diff --check가 통과했다. 배포 실행은 수행하지 않았다.
