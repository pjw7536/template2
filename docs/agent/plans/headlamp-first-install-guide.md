# ExecPlan: Headlamp 최초 설치 가이드 보강

## 목표
- Headlamp 초기화 후 사용자가 실행 위치·입력값·기대 결과를 확인하며 설치를 완료할 수 있게 한다.

## 현재 상태
- deploy/headlamp의 01~06 문서와 README에 설치 명령은 있으나 초보자가 준비물과 단계 간 전달값을 이해하기 어렵다.
- Keycloak 사내 로그인은 정상이며 실제 클러스터의 초기화 범위는 확인하지 않았다.

## 범위
- deploy/headlamp의 README, 01, 환경변수 참고, 03~06 문서.
- 실행 코드·배포 계약·Keycloak 공통 설정은 변경하지 않는다. 기존 다른 작업의 변경을 보존한다.

## 설계
- 실행 위치와 결과물을 먼저 설명하고 기존 명령 주변에 입력 방법·성공 판정·오류 대응을 추가한다.
- 초기화 후 Secret 재등록, client secret과 Secret 이름의 차이, 모든 API server 적용을 명시한다.
- 기본 사내 CA 절차를 유지하며 공개 CA 분기는 실행 전에 선택하게 한다.
- API/env/auth 계약 변경 없음.

## 실행 단계
- [x] 기존 가이드·배포 스크립트·지침 확인
- [x] 단계별 안내 보강
- [x] 링크·Bash 문법·입력 생성·문서 차이 검증

## 검증
- 변경 Markdown 상대 링크의 대상 존재 여부와 Bash 코드 블록을 bash -n으로 검사한다.
- make -s headlamp-setup-env 및 make -s headlamp-oidc-client로 안내값을 확인한다.
- git diff --check와 Headlamp 단위 테스트를 실행한다.
- make server-check APP=headlamp PROFILE=prod를 시도하고 도구 부재 등 한계를 기록한다.
- 운영 클러스터 변경과 실제 로그인을 실행하지 않는다.

## 위험과 대응
- 위험: 삭제됐다고 가정한 공용 인증 설정을 덮어쓸 수 있음.
- 대응: 기존 API server 설정 확인과 설치 방식별 분기를 유지한다.
- 위험: 긴 설명에서 단계가 누락될 수 있음.
- 대응: 문서별 시작 조건·실행 장소·완료 점검을 명시한다.

## 진행 기록
- 2026-09-26: 문서 보강 범위와 검증 계획 작성.
- 2026-09-26: 문서 7개에 초기화 후 시작 조건, 실행 위치, env·인증서·client 입력 방법, 단계별 성공·오류 기준 추가. kubeadm YAML 문자열의 콜론 처리와 기존 목록에 합치는 방법 명시.
- 2026-09-26: 상대 파일 링크 47개, Bash 블록 34개(`bash -n`), YAML 블록 3개(PyYAML 파싱 및 command 문자열 확인) 통과. setup-env·oidc-client 출력과 안내값 일치 확인. Headlamp 단위 테스트 15개 및 git diff --check 통과.
- 2026-09-26: server-check는 helm 실행 파일 부재로 완료하지 못함. 운영 적용·사내망 접속·실제 로그인은 실행하지 않음.
- 2026-09-26: Git 마무리 검증에서 `.tools/bin/helm`을 확인해 PATH에 추가하고 Headlamp server-check 통과. 앞선 도구 탐색 한계를 해소했으며 운영 클러스터 검증은 여전히 별도다.
