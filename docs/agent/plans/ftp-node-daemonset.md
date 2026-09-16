# ExecPlan: 서버별 FTP Kubernetes 배포

## 목표
- 필요한 노드마다 FTP를 실행하고 해당 노드의 파일을 독립적으로 보관한다.

## 현재 상태
- FTP는 기존 infra Compose에만 존재하며 6380, 8076–8079 포트를 사용한다.
- 사내 서버 배포는 Kubernetes 전용이다.

## 범위
- deploy/ftp 원본·운영 안내와 서버 선택 체크아웃·검사를 추가한다.
- Monitoring 전환, 기존 참고용 Compose 삭제, 실제 서버 적용은 포함하지 않는다.

## 설계
- 라벨로 선택한 Linux 노드에 hostNetwork DaemonSet을 실행한다.
- status.hostIP를 passive 주소로 사용하고 노드 로컬 폴더를 마운트한다.
- 계정은 외부 Secret에서 읽으며 API/DB 계약은 바꾸지 않는다.

## 실행 단계
- [x] FTP 원본과 배포 안내 작성
- [x] 서버 검사·선택 체크아웃 연결
- [x] 렌더링 및 회귀 검사

## 검증
- make server-check APP=ftp
- node --test scripts/tests/server-checkout.test.cjs
- bash 구문 검사, git diff --check

## 위험과 대응
- hostNetwork 포트 충돌: 기존 FTP 중단 및 방화벽 범위를 안내한다.
- 데이터는 노드별 독립이며 자동 이관되지 않는다. 기존 폴더를 명시적으로 준비한다.
- 실제 계정·서버가 지정되지 않았으므로 클러스터 적용과 접속 검사는 별도다.

## 진행 기록
- 2026-09-15: FTP DaemonSet 전환 범위 확정.
- 2026-09-15: server-check와 선택 체크아웃 테스트 8개 통과. Bash 구문과 diff 공백 검사 통과.
- 2026-09-15: Docker bridge IP 직접 접근은 환경에서 불가하여 localhost 공개 포트로 이미지 검증. DNS 역조회에 따른 로그인 지연을 확인해 REVERSE_LOOKUP_ENABLE=NO 적용 후 로그인·passive 업로드/다운로드·호스트 파일 저장·비밀번호 로그 미출력 확인. 테스트 컨테이너와 임시 파일 정리 완료.
- 2026-09-15: 검증 이미지 digest 고정. 실제 Kubernetes 배치·사내 방화벽·노드별 접속 검사는 서버에서 별도로 수행해야 한다.
