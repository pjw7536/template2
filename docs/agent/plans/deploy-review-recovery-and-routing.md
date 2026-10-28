# ExecPlan: 추가 deploy 리뷰 4건 수정

## 목표
- Keycloak 재배포의 Namespace 정책과 Retain DB 데이터·인증 복구를 보존한다.
- MinIO 경로 리다이렉트와 Monitoring 선택 구성의 배포 완료 판정을 바로잡는다.

## 착수 당시 상태
- Keycloak은 기존 Namespace에도 최소 manifest와 stack Namespace를 apply한다.
- runtime Secret 부재 방어가 PVC만 확인해 namespace 삭제 뒤 남은 Retain PV를 놓친다.
- Nginx의 /minio 리다이렉트는 내부 HTTP scheme으로 절대 URL을 만든다.
- Monitoring은 비활성화한 Alertmanager 등에도 고정 workload 생성 대기를 수행한다.
- 기존 사용자 staged 변경과 앞선 배포 수정은 보존해야 한다.

## 범위
- 관련 deploy 실행 코드·안내와 기존 단위·tooling 회귀 검사를 수정한다.
- 제품 소스·credential·실제 클러스터·Git index·커밋은 변경하지 않는다.
- PV 데이터 삭제·claimRef 자동 해제·Secret 자동 복원은 수행하지 않는다.

## 설계
- 기존 Namespace는 갱신하지 않고, 없는 경우에만 source의 초기 Namespace를 create한다. 기존 Namespace는 stack 적용 목록에서 제외한다.
- 같은 Namespace 재적용 패턴이 있는 Airflow·FTP와 호환 server-up 경로도 동일하게 보존한다. Keycloak stack을 재적용하는 호환 경로에서는 Namespace를 목록에서 제외한다.
- runtime Secret이 없는데 기존 PVC 또는 PV가 있으면 인증값 생성 전에 중단한다. 남은 볼륨과 DB의 실제 credential을 확인한 뒤 명시적으로 복구하도록 안내한다.
- Nginx의 /minio location은 상대 Location을 반환해 원래 HTTPS·host·port를 보존한다.
- Monitoring 대기 대상은 최종 Helm 구성의 활성 리소스를 기준으로 선택한다. 표준 라이브러리와 기존 도구만 사용하며 CRD 미설치 초기 서버에서도 렌더·검사가 동작해야 한다.
- 사용자 DB schema·인증 endpoint·제품 API 변경은 없다.

## 실행 단계
- [x] Keycloak Namespace 보존과 Retain PV 사전 검사를 수정한다.
- [x] Nginx 상대 리다이렉트와 실제 프록시 회귀 검사를 추가한다.
- [x] Monitoring 선택 구성의 대기·관련 준비 조건을 최종 렌더에 맞춘다.
- [x] 관련 배포·checkout·렌더·문서·구문 검증을 완료하고 결과를 기록한다.

## 검증
- python3 -m unittest discover -s deploy/shared/tests
- PATH="$PWD/.tools/bin:$PATH" python3 -m unittest discover -s deploy/airflow/tests
- PATH="$PWD/.tools/bin:$PATH" python3 -m unittest discover -s deploy/monitoring/tests
- node --test apps/tooling/tests/k8s-routing.test.cjs apps/tooling/tests/portal-deployment.test.cjs apps/tooling/tests/server-checkout.test.cjs
- make k8s-render-local k8s-render-server
- make audit-docs
- git diff --check 및 변경 Python·Nginx 구문 검사
- Namespace 생성 전후·기존 정책 유지·기존 PV 복구 중단·초기 설치·상대 Location·선택 구성 비활성화 시나리오를 검증한다.
- 실제 cluster apply와 DB 복구·접속 검증은 실행하지 않는다.

## 위험과 대응
- 위험: Namespace 보존 수정으로 최초 설치의 namespace가 준비되지 않을 수 있다.
- 대응: source의 Namespace를 별도 create하고 그 뒤 Secret과 stack을 적용한다. 기존 namespace에는 쓰지 않는다.
- 위험: 기존 PV를 신규 볼륨으로 간주해 잘못된 DB 인증값을 등록할 수 있다.
- 대응: PV/PVC 존재 시 runtime Secret 생성 전에 중단하고 실제 인증값·수동 볼륨 복구를 요구한다.
- 위험: 선택 구성 판단이 CRD 내부 kind 문자열을 실제 리소스로 오인할 수 있다.
- 대응: 고정 chart의 최종 리소스 구조를 기준으로 판단하고 CRD만 있는 비활성 렌더도 회귀 검사한다.

## 진행 기록
- 2026-10-28: 추가 리뷰 4건 수정 요청을 기록했다. 시작 index SHA-256은 9e7e31315c685cc6a45705c6cc75ba43cbb836b1eef6d4b6827f597271349c39다.
- 2026-10-28: Namespace 정책 보존을 Keycloak 전용 명령뿐 아니라 같은 잘못된 apply 패턴이 확인된 Airflow·FTP·호환 server-up 호출부에도 적용한다.
- 2026-10-28: Keycloak·FTP의 최종 적용 목록에서 Namespace를 제외하고, 없는 경우에만 원본 metadata로 생성한다. Airflow의 전용·호환 경로도 기존 Namespace를 수정하지 않는다.
- 2026-10-28: Keycloak runtime Secret이 없고 PV/PVC가 남아 있으면 모든 변경 전에 중단한다. Secret 복원 후에도 Released PV 또는 이전 claimRef UID가 남아 있으면 수동 복구를 요구한다. 데이터·claimRef는 자동 변경하지 않는다.
- 2026-10-28: /minio에 상대 Location을 적용했다. 실제 Nginx에서 전달 scheme과 요청 host·port 조합 6개 및 기존 upstream 경로를 검사했다.
- 2026-10-28: Monitoring은 고정 chart 최종 렌더의 최상위 리소스만 해석해 활성 서비스·실제 이름을 결정한다. 비활성 서비스의 PV·Grafana Secret 조회와 Operator workload 대기를 생략하고, 모든 서비스 비활성화 시 빈 스토리지 목록을 적용하지 않는다. CRD 내부 kind 오인 방지와 이름 override도 회귀 검사한다.
- 2026-10-28: 관련 검사 177개(shared 84, Airflow 45, Monitoring 15, Node 33)가 통과했다. Node 검사에는 실제 Nginx 응답과 deploy만 선택한 sparse checkout 시나리오가 포함된다. local/server Kustomize 렌더와 문서·Python 구문·공백 검사도 통과했다.
- 2026-10-28: 완료 시 index SHA-256은 시작 값과 같다. 실제 클러스터 적용·DB 복구·접속 검증·커밋은 실행하지 않았다.
