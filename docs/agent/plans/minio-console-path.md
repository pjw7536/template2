# ExecPlan: MinIO 콘솔 하위 경로 공개

## 목표
- Portal 도메인의 `/minio-console/`에서 MinIO 계정으로 콘솔에 로그인한다.

## 현재 상태
- Portal nginx의 `/minio/`는 파일 API(9000)를 전달한다.
- 콘솔 전용 Ingress와 공용 file middleware를 추가해 MinIO:9001로 직접 연결한다.

## 범위
- 공용·로컬 Traefik, 콘솔 전용 Ingress, 운영·로컬 MinIO env, 실행 안내를 변경한다.
- 기존 파일 API 경로와 계정, Headlamp 인증은 변경하지 않는다.

## 설계
- 콘솔 전용 Ingress가 Traefik에서 MinIO Service의 console(9001)로 직접 전달한다.
- 공용 file provider의 middleware가 마지막 슬래시 리다이렉트와 접두사 제거를 담당한다.
- middleware ConfigMap은 deploy/shared/ingress/middlewares에서 운영·로컬이 재사용한다. 추가 CRD나 권한은 필요하지 않다.
- 앞서 추가한 nginx 콘솔 경로는 제거한다.
- MINIO_BROWSER_REDIRECT_URL에 외부 도메인과 `/minio-console/`을 지정한다.
- 기존 MinIO 인증을 사용하며 DB/API 코드 변경은 없다.
- 운영 MinIO와 초기화 Job은 사용자 지정 Worker khplanew01(10.172.40.117)에 고정한다. 로컬 overlay는 기존 kind Worker로 덮어쓴다.
- 데이터 디스크 위치는 미정이며 PV의 노드 조건을 해당 Worker와 일치시킨다. 임의의 운영 PV 생성이나 데이터 이동은 수행하지 않는다.

## 실행 단계
- [x] 직접 라우팅 및 공통 middleware 반영
- [x] 배포·접속 안내 갱신
- [x] 렌더·서버 검사와 가능한 런타임 검증
- [x] 운영 Worker 고정·로컬 호환·배포 현황 문서 갱신 및 렌더 검증

## 검증
- make server-check APP=portal PROFILE=prod
- make k8s-render-local
- make env-profile-key-check ENV_APP=portal ENV_PROFILE=local
- make server-check APP=keycloak PROFILE=prod
- node --test apps/tooling/tests/server-checkout.test.cjs
- 실제 Traefik 이미지로 콘솔 HTTP 경로와 로그인 검증

## 위험과 대응
- 이미지별 콘솔 하위 경로 동작 차이: 사용 가능한 로컬 이미지로 확인한다.
- 실제 서버의 도메인·TLS·계정은 운영 env를 통해 설정한다.

## 진행 기록
- 2026-10-13: MinIO 공식 저장소의 하위 경로 안내를 확인했다. 콘솔 URL env와 접두사 제거 프록시를 함께 적용한다.
- 2026-10-13: 서버 검사, 로컬 전체 Kustomize 렌더, 로컬 env 키 검사 통과.
- 2026-10-13: 격리된 임시 Docker 네트워크에서 nginx 1.27 및 캐시된 MinIO RELEASE.2025-09-07T16-13-09Z로 구문, 슬래시 리다이렉트, HTML base, JavaScript 자산, 로그인·세션 쿠키, 인증된 버킷 조회, 기존 파일 API health 경로를 검증했다. 임시 컨테이너와 네트워크는 제거했다.
- 2026-10-13: 실제 운영 배포·브라우저 업로드·다운로드·WebSocket 통합 검증은 미실행이다. 운영 도메인/TLS 및 env 값 적용 후 배포 안내의 확인 절차를 따른다.
- 2026-10-26: 사용자 지적에 따라 Traefik 직접 연결로 전환한다. 기존 Ingress provider를 유지하고 file provider로 경로 middleware를 제공한다. 공용 controller 재배포 시 설정이 유지되도록 운영 원본과 로컬 집계에 함께 반영한다.
- 2026-10-26: Portal·Keycloak server-check, 로컬 Kustomize 렌더, 로컬 env 키 검사, git diff --check 통과. 선택 checkout 검사 17개 통과. Keycloak 전달 YAML도 make k8s-export로 갱신했다.
- 2026-10-26: 운영·로컬 렌더 결과에서 Ingress의 MinIO console 포트 직접 참조와 controller의 해시 ConfigMap 마운트를 확인했다. nginx.conf는 HEAD와 동일해 콘솔 변경이 완전히 제거되었다.
- 2026-10-26: 격리된 Docker 네트워크에서 실제 Traefik v3.7.1과 공통 middleware 파일을 사용해 화면·JavaScript, 슬래시 리다이렉트 및 query 보존, 잘못된 로그인 거부, 로그인·세션 쿠키, 인증된 버킷 조회, 콘솔 외 경로 제외를 확인했다. 최초 검증에서 file provider의 chain 참조 형식 오류를 발견해 문자열 목록으로 수정한 후 통과했다. 임시 컨테이너와 네트워크는 제거했다.
- 2026-10-26: 런타임 검증의 router·service는 임시 file 설정이다. 실제 Kubernetes Ingress 및 운영 TLS·도메인·WebSocket·업로드/다운로드의 통합 검증은 미실행이며 운영 클러스터는 변경하지 않았다.
- 2026-10-26: MinIO가 없는 기존 클러스터용 MINIO_SETUP.md를 추가했다. 10Gi PVC 준비, 관리자 입력·Secret, MinIO 생성, 기존 인증서 복사, 기존 controller만 수정하는 file provider·namespace 감시·RBAC, 콘솔 Ingress 순서를 설명한다. Keycloak·Portal 전체 재배포가 필요하다는 앞선 안내를 보완했다.
- 2026-10-26: MINIO_SERVER_URL은 경로 접두사를 허용하지 않는 내부 콘솔 연결 주소이므로 운영 예시의 /minio 경로를 제거하고 운영·로컬 모두 http://minio:9000으로 정합성을 맞췄다. 공식 서버 소스와 실제 캐시 이미지에서 기동·로그인으로 확인했다. Portal server-check, 로컬 env 키 검사, 전체 로컬 렌더 및 diff 검사를 다시 통과했다.
- 2026-10-27: 사용자가 khplane01w09는 Keycloak 전용, MinIO 배포 대상은 khplanew01이라고 지정했다. base의 MinIO·초기화 Job을 고정해 단독 apply에도 적용되도록 하며, 로컬 Job patch를 함께 맞춘다. 단일 데이터 디렉터리의 동시 사용을 피하도록 Deployment 전략은 Recreate로 한다.
- 2026-10-27: Portal server-check, 전체 로컬 Kustomize 렌더, diff 검사 통과. base·운영 overlay의 Deployment/Job은 khplanew01, 로컬 Portal·전체 집계는 tailwind-local-worker로 렌더됨을 확인했다. 운영 디스크 경로·PV 생성과 실제 서버 배포는 미실행이다.
