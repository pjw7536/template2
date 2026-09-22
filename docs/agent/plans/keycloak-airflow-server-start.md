# ExecPlan: 기존 Keycloak과 Airflow 서버 기동

## 목표
- 기존 Keycloak을 유지하고 저장소 pull 뒤 한 진입점에서 Keycloak·Airflow를 재적용한다.
- 같은 서버 Traefik과 기존 DNS의 /airflow 경로를 사용한다.

## 현재 상태
- Keycloak 스택에 Traefik이 포함되어 있고 etch-sso만 감시한다. Portal 패치는 재적용에 취약하다.
- Airflow Helm 배포는 있지만 공용 Traefik 감시·namespace 권한 연결은 없다.
- 실제 사내 kubeconfig·이미지·TLS·env는 서버에 있고 현재 작업 폴더는 외부 PC다.

## 범위
- 공용 ingress 소유권·서버 실행 도구·선택 checkout·문서·회귀 테스트.
- 기존 Keycloak namespace·이름·DB·인증설정과 credential은 유지한다. 실제 클러스터·Git remote는 변경하지 않는다.

## 설계
- Traefik 소스는 deploy/shared/ingress로 이동하고 기존 Keycloak Kustomize/전달 YAML 호환성은 유지한다.
- 새 server-up은 적용 전에 기존 Traefik 감시 범위를 읽고 필요한 namespace를 합친다. 권한을 먼저 생성하고 재적용한다.
- 기존 Keycloak Secret·TLS·Deployment 존재를 확인하며 자동 자격증명 교체나 OIDC/mapper 실행은 하지 않는다.
- Airflow는 실제 env와 준비된 chart/image를 사용하며 이번 UI 기동 단계에만 신규 DAG 일시정지 override를 적용한다.
- 외부 URL·TLS는 env 입력이며 기존 Portal domain 또는 기존 Keycloak domain의 /airflow를 선택할 수 있다.

## 실행 단계
- [x] 기존 controller 소스를 공용 경로로 이동하고 렌더 동등성 확인
- [x] 서버 기동·Traefik 권한/감시 연결 구현
- [x] 첫 기동 모드·선택 checkout·명령 안내 연결
- [x] 회귀·렌더·재실행·실패 경로 검증

## 검증
- 이전/이후 Keycloak Kustomize 리소스 의미적 동일성
- 기존 감시 namespace 보존·권한 적용 순서·Secret 미변경·새 DAG pause 회귀
- node --test scripts/tests/*.test.cjs 및 Airflow 단위/Helm 통합
- 문서·쉘/Python 문법·git diff --check

## 위험과 대응
- Portal API가 없으므로 신규 DAG를 일시정지한다. 복원한 DB의 기존 활성 DAG는 자동 변경하지 않는다.
- TLS는 다른 도메인 인증서를 임의 재사용하지 않고 Airflow namespace의 지정 Secret을 요구한다.
- 사내 env·이미지·차트·디스크 최초 준비는 pull과 별개이며 문서에 구분한다.

## 진행 기록
- 2026-09-14: 사용자 목표를 기존 Keycloak + Airflow UI 기동으로 좁혀 진행.
- 2026-09-14: Keycloak Kustomize의 이동 전후 리소스 동등성 확인, 전달 YAML 재생성, APP=keycloak-airflow 정적 검사 통과.
- 2026-09-14: 서버 기동 단위 테스트 11개, Airflow 단위·실제 Helm 검사 18개, 전체 Node 회귀 45개 통과. OpenSSL 실제 인증서 hostname 일치·불일치와 mocked kubectl의 적용 순서·재실행을 검증했다.
- 2026-09-14: 문서 감사, Bash/Python 문법, git diff --check 통과. 사내 클러스터 배포·사내 이미지 빌드·Git commit/push는 실행하지 않았다. 최초 env·이미지·디스크·TLS 준비와 이후 pull 경로는 deploy/SERVER_START.md에 기록했다.
