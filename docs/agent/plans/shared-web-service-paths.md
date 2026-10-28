# ExecPlan: 공용 도메인의 서비스별 웹 경로 정합성

## 목표
- Keycloak은 `etch-sso.samsungds.net`, 나머지 웹 서비스는 `etch.samsungds.net`의 서비스별 경로로 제공한다.
- 저장소의 기본 배포 입력·라우팅·문서·검증을 같은 계약에 맞춘다.

## 현재 상태
- Portal·MinIO의 운영 host와 공개 URL은 placeholder다.
- Airflow는 `/airflow` 코드를 갖췄지만 기본 env는 port-forward·DB 로그인이다.
- Headlamp와 Keycloak의 운영 도메인은 이미 정합하다.
- Monitoring은 Ingress 없이 port-forward만 제공하며 공용 controller 연결 코드가 없다.

## 범위
- `deploy/portal`, `deploy/airflow`, `deploy/monitoring`, 관련 공통 배포 안내·검사.
- 공통 설정을 재사용하는 local의 실행 호환성 확인과 필요한 override.
- 실제 클러스터 배포·인증서 발급·DB 입력·기존 credential 변경은 하지 않는다.

## 설계
- Portal `/`, API `/api`, callback `/auth`, MinIO `/minio`, 콘솔 `/minio-console`을 기존 경로대로 유지한다.
- Airflow `/airflow`와 Keycloak issuer를 운영 기본값으로 설정한다. 미입력 client secret은 배포 전 검증으로 차단한다.
- Monitoring env로 공용 host·TLS Secret·Ingress 활성화를 주입한다. `/grafana`, `/prometheus`, `/alertmanager`를 각각 앱의 외부 URL·경로 설정과 함께 렌더한다.
- Monitoring 배포는 TLS·공용 Traefik을 사전 확인하고 namespace RBAC와 감시 목록만 추가한다. 기존 VIP·배치·다른 앱 감시를 보존한다.
- DB/PV/계정은 보존하고 local은 사내 DNS를 사용하지 않게 별도 override한다. 제품 API·DB schema는 변경하지 않는다.

## 실행 단계
- [x] Portal·Airflow 운영 주소 정합성 수정
- [x] Monitoring 경로·공용 controller 연결 및 회귀 검사 구현
- [x] 운영 문서와 local 호환성 정리
- [x] 정적 검사·고정 chart 렌더·관련 테스트 실행 및 결과 기록

## 검증
- `make server-check APP=all PROFILE=prod`
- Portal web 환경값 검사와 API 환경값 검사(기존 DB·Secret 미입력은 구분해 기록)
- Airflow·Headlamp·Monitoring·공용 Ingress 관련 Python unittest
- `node --test apps/tooling/tests/server-checkout.test.cjs`
- local 설정·렌더 검사 중 변경 계약과 관련된 검사
- 고정 chart 렌더에서 host·path·TLS·callback·서비스 외부 URL 확인

## 위험과 대응
- 위험: 하위 경로 불일치로 정적 파일·리다이렉트·Prometheus scrape가 실패할 수 있다.
- 대응: 앱 내부 route prefix와 외부 URL을 함께 설정하고 고정 chart 렌더 및 기본 scrape 경로를 검증한다.
- 위험: 공용 controller 갱신이 기존 VIP나 감시 namespace를 잃을 수 있다.
- 대응: 기존 `routing.namespace_patch/namespace_access`를 재사용하고 동시 변경 검사 및 기존 배치 보존을 테스트한다.
- 위험: 운영 도메인을 기본값으로 바꾸면 local에 유입될 수 있다.
- 대응: local 설정 합성에서 사내 도메인·Ingress 설정을 명시적으로 override한다.

## 진행 기록
- 2026-10-28: 요청 범위를 공용 도메인의 웹 경로 정합성으로 확정했다. 모니터링 경로는 `/grafana`, `/prometheus`, `/alertmanager`를 사용한다.
- 2026-10-28: Portal·MinIO Ingress와 공개 URL·callback에 확정 도메인을 적용했다. Airflow는 HTTPS 공용 경로·Keycloak 모드를 기본값으로 바꿨으며 실제 client secret은 입력 전까지 배포 검사에서 차단한다.
- 2026-10-28: Monitoring의 앱 내부 route prefix·외부 URL·Ingress와 TLS/RBAC 사전 검사를 구현했다. 고정 chart가 datasource·self-scrape·Alertmanager 연결에도 prefix를 반영하는 것을 실제 렌더로 확인했다.
- 2026-10-28: local은 localhost 인증·port-forward 설정을 유지하도록 명시적으로 override했다. mock endpoint·인증 응답 계약은 바뀌지 않아 mock 변경은 필요하지 않았다.
- 2026-10-28: 임시 `/tmp/tailwind-web-routing-tools/linux-amd64/helm`의 Helm 3.19.0과 저장소 고정 chart로 `make server-check APP=all PROFILE=prod`를 통과했다. 도구는 저장소에 추가하지 않았다.
- 2026-10-28: Python 테스트 Airflow 45개·Monitoring 20개·Headlamp 15개·공용 배포 84개·local runtime 4개와 server-checkout Node 테스트 28개, 총 196개를 통과했다.
- 2026-10-28: `make k8s-check`, `make k8s-render-local`, Portal prod web 환경값 검사, `git diff --check`를 통과했다. 최종 Ingress 전체를 함께 렌더해 도메인·TLS host·경로와 중복 여부를 확인했다.
- 2026-10-28: `make prod-profile-env-check`는 기존 미입력 `DJANGO_SECRET_KEY`, `DJANGO_DB_NAME/USER/PASSWORD/HOST` 때문에 실패한다. 이번에 변경한 DNS·callback 관련 오류는 해소됐다. 실제 배포·브라우저 로그인·TLS 검증은 실행하지 않았다.
