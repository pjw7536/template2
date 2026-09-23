# ExecPlan: deploy 잔재 정리와 운영 기본값 검증

## 목표
- 불필요한 이전 배포 경로·중복 안내를 정리하고 확인된 운영값을 기본 입력에 반영한다.
- 서버에서 입력을 반복하지 않도록 기존 환경설정·인증서 연결을 맞춘다.

## 현재 상태
- Headlamp issuer 예시값과 CA 공백, Keycloak 구 인증서 기본 경로가 남아 있다.
- 인증서 공용 폴더와 OIDC 가이드에 이전 턴의 미커밋 변경이 있다. 보존한다.
- 전체 앱의 실행 원본과 rendered YAML·CI 정의는 현재 진입점에서 사용한다.
- Portal 이미지·도메인, Airflow 이미지·노드, Monitoring 노드·K8S 미러 등은 확정 기록이 없어 사용자에게 요청했다.
- 사내 context는 없고 로컬 context만 있어 실제 사내 배포 검증은 불가하다.

## 범위
- deploy 인증서 안내·기본 경로·확인된 비밀값 없는 운영 설정·관련 Makefile과 테스트.
- 실제 credential을 만들거나 기존 DB·Secret을 교체하지 않는다.
- 사용 중인 CI·생성 YAML·공용 배포 진입점은 참조 근거 없이 삭제하지 않는다.

## 설계
- 공용 사이트별 certs를 단일 인증서 안내로 사용하고 구 certs 안내는 제거한다.
- TLS 문서에는 앱별 적용 차이만 남기고 추출·검증은 공용 안내를 연결한다.
- Headlamp 예시에 확인된 issuer·CA 이름을 넣고 실제 env가 없으면 비밀값 없는 운영 예시를 기본으로 사용한다.
- 미확정 값은 운영값으로 위장하지 않고 검사 결과·필요 입력을 기록한다.

## 실행 단계
- [x] 전체 deploy 원본·예시·호출 관계와 미확정 값 조사
- [x] 확정된 기본값과 인증서 잔재 정리
- [x] 앱별 검사·단위 테스트·서버 경계·문서 링크 검증
- [x] 미확정 입력과 실제 서버 검증 한계 기록
- [ ] 사용자에게 운영 설정을 받아 나머지 임시값 교체

## 검증
- make server-check APP=all PROFILE=prod (고정 chart·Helm 반입 후)
- 앱별 Python 단위 테스트와 node --test apps/tooling/tests/server-checkout.test.cjs
- 관련 배포·문서 검사 및 git diff --check
- 구 인증서 경로·예시값 잔여 검색과 실제 Secret 없는 렌더 검증

## 위험과 대응
- 새 주소·이미지·노드를 추측하면 배포 실패·데이터 이동 가능: 확인된 값만 반영한다.
- 예시 검사 성공은 실행 환경 준비·인증 성공과 다름: 검사 수준을 구분한다.
- 실제 운영 파일은 Git 제외 상태를 보존한다.

## 진행 기록
- 2026-09-22: deploy 전체 참조 조사 시작. 미확정 입력을 비동기로 질문함.
- 2026-09-22: 구 Keycloak certs README를 제거하고 인증서 추출·검증 안내를 shared/certs/README.md로 통합했다. 기본 인증서 경로도 사이트별 폴더로 변경했다.
- 2026-09-22: Headlamp issuer·CA와 확인된 Monitoring Docker/Quay/GHCR 미러를 반영했다. Headlamp는 별도 env가 없으면 운영 기본값이 들어간 예시 파일을 사용하고 기존 env가 있으면 우선한다.
- 2026-09-22: 고정 버전 chart와 Helm을 /tmp로 내려받아 make server-check APP=all PROFILE=prod의 6개 앱 검사를 통과했다. 예시 입력의 정적 검사·렌더 결과이며 운영 서버 정상 동작을 보장하지 않는다.
- 2026-09-22: 관련 Node 검사 58개, Headlamp Python 검사 12개, shared Python 검사 31개 통과. make headlamp-check와 headlamp-oidc-client 생성도 별도 env 없이 성공했다.
- 2026-09-22: make k8s-export 후 생성 YAML 차이가 없었다. deploy 문서 상대 링크 누락 0건, 셸 문법 검사와 git diff --check 통과. 구 인증서 경로 잔여 참조도 제거했다.

## 남은 운영 입력과 검증 한계
- Portal: 공개 도메인, API/Web 이미지 주소·태그와 기존 운영 환경설정.
- Airflow: DAG 포함 운영 이미지 주소·태그, 배치 노드, 관리자 이메일 및 기존 인증 설정.
- Monitoring: 배치 노드, registry.k8s.io 사내 미러 주소.
- 비밀번호·토큰·OIDC client secret은 기존 서버 파일·Kubernetes Secret이 필요하다. 임의 값을 실제 credential로 간주하지 않았다.
- 현재 접근 가능한 context는 kind-tailwind-local뿐이고 실제 인증서도 없다. 운영 클러스터 배포, TLS 연결, Keycloak 로그인·RBAC 검증은 실행하지 않았다.
- 기존 서버 env는 보존하므로 해당 파일에 구 값이 있으면 새 기본값보다 우선한다. 운영 파일 위치와 내용을 확인하기 전에는 서버의 환경변수 수정이 모두 불필요하다고 판단할 수 없다.
