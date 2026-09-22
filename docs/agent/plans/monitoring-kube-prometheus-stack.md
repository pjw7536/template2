# ExecPlan: Kubernetes 전용 Monitoring

## 목표
- Portal과 독립적인 kube-prometheus-stack 신규 배포를 준비한다.
- 사내 미러 이미지와 고정 Helm chart로 서버에서 설치한다.

## 현재 상태
- Monitoring은 이전 Compose만 있고 server-check가 실패한다.
- Keycloak·Airflow·FTP 원본은 이미 존재하며 현재 staged 변경은 보존한다.

## 범위
- deploy/monitoring, 서버 검사·선택 체크아웃 테스트, 배포 안내와 Makefile.
- Portal·인증·업무 DAG·기존 Compose 동작은 변경하지 않는다.

## 설계
- 고정 chart와 SHA-256, 공통 values와 공개 env 예시, Python 배포 도구.
- Grafana 기존 Secret 참조, port-forward 접속, 외부 알림 수신자 미설정.
- 서버별 노드·local PV 경로·이미지 registry를 외부 입력으로 지정한다.
- Prometheus Operator CRD와 cluster 수집 권한을 설치하며 기존 Operator가 있으면 독립 설치를 중단한다.

## 실행 단계
- [x] chart와 의존 이미지 확인
- [x] 설정·렌더·배포·서버 진입점 구현
- [x] 문서·회귀 검사 갱신
- [x] 실제 chart 렌더·테스트 실행

## 검증
- Monitoring 실제 Helm lint/template, 이미지 경로·영구 저장소 검증
- deploy/monitoring/tests 단위 테스트와 scripts/tests/server-checkout.test.cjs
- 클러스터 적용은 수행하지 않는다.

## 위험과 대응
- 기존 공용 모니터링과 충돌: 최초 설치 시 기존 Prometheus Operator CRD 확인.
- 파일 소실: local PV Retain, 경로 사전 준비 및 배치 고정.
- 사내 미러 누락: 모든 렌더 이미지 목록을 출력해 사전 확인.

## 진행 기록
- 2026-09-15: 신규 Monitoring 구성 작업 시작. 실제 설치·commit·push는 실행하지 않는다.

- 2026-09-15: chart 91.4.0과 SHA-256 고정, 4종 upstream 미러를 env 입력으로 분리. Prometheus 20Gi·Alertmanager 2Gi·Grafana 5Gi Retain local PV 구성.
- 검증: Helm 실제 lint/template 및 make server-check APP=monitoring 통과(로컬 Helm 3.19+ 경로 지정).
- 검증: Node 배포·선택 checkout·환경 회귀 42개 통과, 최종 Monitoring Python 테스트 8개 통과.
- 검증: git diff --check, Bash 문법, scripts/agent/check_docs_inventory.sh 통과.
- 실제 사내 image pull·클러스터 설치·Targets UP은 서버에서 검증해야 한다. 배포·commit·push 미실행.
