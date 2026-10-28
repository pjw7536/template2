# ExecPlan: 배포 사전 검사와 초기화 오류 수정

## 목표
- 확인한 5가지 배포 오류를 수정하고 실패 재현을 회귀 테스트로 고정한다.

## 현재 상태
- 수정 전 회귀 테스트 75개에서 놓친 오류를 별도 실패 테스트로 재현했다.
- Airflow Fernet Secret 누락, TLS 개인키 불일치, 미허용 taint를 사전 검사에서 차단한다.
- MinIO 버킷 생성 오류를 전파하고 초기화를 300초로 제한하며 health probe가 handler까지 도달한다.
- 기존 문서·MinIO·Ingress 미커밋 변경을 보존했다.

## 범위
- deploy/airflow, deploy/shared의 사전 검사와 해당 테스트.
- deploy/portal 공통 Kubernetes 정의와 apps/tooling의 관련 회귀 테스트.
- 관련 운영 문서. 실제 클러스터·DB·Secret·앱 업무 코드는 변경하지 않는다.

## 설계
- 기존 DB PVC·metadata Secret·scheduler/webserver/triggerer가 있으면 Fernet Secret 복원을 먼저 요구한다.
- TLS 인증서·개인키의 공개키를 비교하며 비밀값은 인자로 전달하거나 출력하지 않는다.
- Airflow와 내부 PostgreSQL의 최종 toleration에서 허용하지 않는 차단 taint를 거부한다. Helm override 반영은 [추가 리뷰 후속 수정](deployment-review-followups.md)을 따른다.
- MinIO 초기화는 기존 버킷을 허용하되 다른 실패는 전파하고 실행 시간을 제한한다.
- API·Nginx health probe에 HTTPS 전달 헤더를 추가해 실제 health handler의 응답을 검사한다.

## 실행 단계
- [x] 실패 조건과 정상·신규 설치 회귀 테스트 추가
- [x] 배포 검사·manifest 수정
- [x] 문서 동기화와 로컬·서버·선택 checkout 검사

## 검증
- Airflow·공통 배포 Python 단위 테스트와 실제 OpenSSL 키 일치 검사
- MinIO 초기화의 신규·기존 버킷·오류 전파 테스트
- Docker Compose api의 Django middleware로 렌더된 probe 동작 검증
- `PATH="$PWD/.tools/bin:$PATH" make tooling-test`
- `make k8s-render-local`, `PATH="$PWD/.tools/bin:$PATH" make server-check APP=all`
- `make audit-docs`, `git diff --check`

## 위험과 대응
- 기존 Fernet Secret이 사라진 환경은 새 키를 자동 적용하지 않고 원래 키 복원 후 재시도한다.
- 실제 외부 DB에만 남은 과거 데이터는 클러스터 이력 없이 판별할 수 없어 운영 복원 절차에 원래 키 준비를 명시한다.
- probe 헤더는 기존 reverse proxy 계약을 재사용하며 보안 설정을 완화하지 않는다.
- 공통 base 수정은 로컬 overlay까지 렌더해 확인한다.

## 진행 기록
- 2026-10-27: 5개 수정 범위·데이터 보존·검증 방법 확정.
- 2026-10-27: 수정 전 Airflow 7개·공통 TLS 3개 실패 사례와 Portal 테스트 2개의 실패를 확인했다. 수정 후 Airflow Python 33개, 공통 배포 Python 49개, tooling 77개 테스트가 통과했다.
- 2026-10-27: 실제 OpenSSL 인증서와 다른 알고리즘의 개인키 불일치를 검증했다. Docker Compose api에서 HTTPS 강제 전환을 켜고 로컬·운영의 실제 probe 8개가 health handler에 도달해 200을 반환하는지 확인했다.
- 2026-10-27: 로컬 Kubernetes 진입점 7개 렌더링, 6개 앱 서버 원본 검사, 앱 소스·local 없는 선택 checkout 검사(tooling 포함), 문서 검사와 diff 공백 검사를 통과했다. 실제 클러스터에는 적용하지 않았다.
