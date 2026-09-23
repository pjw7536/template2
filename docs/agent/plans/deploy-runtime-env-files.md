# ExecPlan: 실제 배포 env 파일 저장

## 목표
- 현재 작업공간에 실제 배포 env를 저장하고 Headlamp Makefile의 example 자동 대체를 제거한다.

## 현재 상태
- Portal·Keycloak의 실제 env는 이미 존재한다. 기존 값을 보존한다.
- Airflow·Monitoring·Headlamp는 example만 있어 실제 env를 생성한다.

## 범위
- 실제 env 파일 생성, Headlamp 실행 경로, 관련 안내.
- example은 초기화·정적 검사 원본으로 유지한다. 운영 env의 기존 Git 제외 규칙도 유지한다.

## 설계
- 기존 파일은 덮어쓰지 않고 누락된 env만 배타적으로 생성한다.
- 파일 권한은 새 env에만 0600을 적용한다.
- 미확정 운영값은 추측하지 않는다.

## 실행 단계
- [x] 실제 env 생성과 실행 경로 수정
- [x] 안내 수정과 검증

## 검증
- 생성 파일 존재·권한·Git 제외 확인, Headlamp 설정 검사와 관련 단위 검사.
- git diff --check.

## 위험과 대응
- Git 제외 파일은 서버 checkout에 전달되지 않는다. 서버로 별도 복사해야 함을 안내한다.
- 실제 서버의 기존 파일은 덮어쓰지 않는다.

## 진행 기록
- 2026-09-23: 요청에 따라 실제 env 파일 저장 작업 시작.
- 2026-09-23: Airflow build/k8s, Monitoring k8s, Headlamp k8s env 4개를 생성했다. Portal 3개와 Keycloak 기존 env는 보존했다. 새 파일은 0600으로 저장하고 Git 제외를 확인했다.
- 2026-09-23: Makefile은 Headlamp 실제 env만 사용한다. make headlamp-check, Headlamp 단위 테스트 12개, git diff --check 통과. 실제 서버 연결 검사는 실행하지 않았다.
- 2026-09-23: Airflow·Monitoring 미확정 값은 기존 입력 그대로이며 파일 생성만으로 운영 준비가 완료되지는 않는다.
