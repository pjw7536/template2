# ExecPlan: 서버 Headlamp 추가

## 목표
- Keycloak 연동 없이 서버에서 토큰 로그인으로 Headlamp를 사용한다.

## 현재 상태
- 로컬 Headlamp는 view와 nodes/namespaces 조회 권한을 사용한다.
- 서버 Monitoring은 고정 Helm chart와 localhost port-forward를 사용한다.
- 작업 폴더에 기존 로컬 Kubernetes 변경이 있으며 보존한다.

## 범위
- deploy/headlamp, 앱 목록, Makefile, 서버 검사와 배포 문서.

## 설계
- 공식 chart 0.45.0과 SHA-256을 고정하고 이미지 registry는 env로 입력한다.
- 기존 로컬과 동일한 조회용 ServiceAccount를 별도로 두고 Pod에는 관리자 권한을 부여하지 않는다.
- OIDC와 Ingress는 비활성화하고 localhost:4466으로 접속한다.
- 서버 선택 checkout에서 local 없이 실행한다.

## 실행 단계
- [x] chart·설정·배포 도구 추가
- [x] 서버 앱 등록·문서 연결
- [x] 렌더링·권한·실패 경로 검사

## 검증
- make server-check APP=headlamp
- python3 -m unittest discover -s deploy/headlamp/tests -v
- 앱 목록·선택 경로 확인과 git diff --check

## 위험과 대응
- chart 기본 cluster-admin 권한은 명시적으로 비활성화한다.
- 실제 서버 배포는 context와 사내 registry 입력이 필요하다. 이번 작업에서는 정적 렌더링까지 검증한다.

## 진행 기록
- 2026-09-16: 기존 로컬 권한 계약을 서버에 적용하기로 결정.

- 2026-09-16: server-check, Python 입력/실패 경로 3건, Node 렌더·독립 실행 2건, diff 공백 검사 통과. 실제 클러스터 배포·로그인은 실행하지 않음.
