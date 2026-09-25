# ExecPlan: FTP 배포 절차

## 목표
- Keycloak처럼 준비·검사·배포·확인을 문서와 Make 명령으로 제공한다.

## 현재 상태
- FTP는 라벨 기반 DaemonSet, hostNetwork, 노드별 hostPath를 사용한다.
- 기존 README는 수동 kubectl 절차만 제공한다. Keycloak 관련 사용자 변경이 존재한다.

## 범위
- deploy/ftp 문서·실행 스크립트, 루트 Makefile, deploy/shared/tests의 회귀 검사.
- 기존 Kubernetes 저장·계정 계약과 Keycloak 변경은 유지한다.

## 설계
- 명시적 context·전체 대상 노드 목록·외부 credential 파일을 입력받는다.
- 검사는 조회만 수행하고, 배포는 namespace → 없는 Secret 생성 → 라벨 → 원본 적용 → rollout 순서로 실행한다.
- 기존 Secret 불일치와 대상 목록 밖의 FTP 라벨 노드는 변경 전에 거부한다.
- 외부 credential은 셸로 실행하지 않고 파싱하며 오류 출력에 값을 노출하지 않는다.

## 실행 단계
- [x] 배포 스크립트·Make 진입점 구현
- [x] 번호별 설치·운영 문서 작성
- [x] 회귀 검사와 정적 검사 실행

## 검증
- python3 -m unittest discover -s deploy/shared/tests -p 'test_ftp_up.py'
- make server-check APP=ftp PROFILE=prod
- node --test apps/tooling/tests/server-checkout.test.cjs
- 실제 클러스터 배포·FTP 전송은 운영 입력이 없어 실행하지 않는다.

## 위험과 대응
- 잘못된 노드 배치: 기존 라벨 포함 전체 목록을 명시하고 Ready·taint·Linux worker 조건 확인.
- 기존 계정 변경: 일치 검사 후 없는 Secret만 create한다.
- 원격 디스크·방화벽은 조회로 보장 불가: 작업 위치와 수동 전송 검증을 명시한다.

## 진행 기록
- 2026-09-25: 기존 Keycloak 패턴과 FTP 원본을 확인하고 설계했다.
- 2026-09-25: FTP 회귀 테스트 10개, 서버 원본 검사, 선택 checkout 테스트 17개 통과. 문서 상대 링크·diff 공백 검사와 Make 진입점 확인도 통과했다. 실제 클러스터 배포·전송 검증은 운영 입력이 없어 실행하지 않았다.
