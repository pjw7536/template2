# ExecPlan: Keycloak Kubernetes 역할별 파일 정리

## 목표
- 기본 기동·사내 OIDC·사용자 매핑 파일을 역할별 폴더로 나눈다.

## 현재 상태
- k8s 루트에 9개 파일이 있으며 모두 참조되고 있다.
- 루트 Kustomize는 서버와 설정 ConfigMap을 생성하고 Job은 별도 실행한다.

## 범위
- 파일 이동, Kustomize·전달 파일 생성 스크립트·실행 안내·테스트 경로 수정.
- Kubernetes 이름·이미지·Secret·DB·실행 로직은 유지한다.

## 설계
- server: stack.yaml, etch-realm.json
- oidc: oidc-setup-job.yaml, setup-oidc.sh, admin-common.sh
- claims: claim-mappers-job.yaml, sync-oidc-claim-mappers.sh, account-user-profile.json
- k8s/kustomization.yaml 진입점과 컨테이너의 ConfigMap 파일명은 유지한다.

## 실행 단계
- [x] 기존 렌더 보관 후 파일 이동과 참조 수정
- [x] 폴더 안내 추가와 전달 YAML 재생성
- [x] 렌더 동일성·설정 Job·배포 회귀 검사

## 검증
- 이동 전후 kubectl kustomize 출력 비교
- 전달 YAML 두 파일의 이동 전후 비교
- make server-check APP=keycloak
- Node 환경설정·라우팅·서버 배포 회귀 검사

## 위험과 대응
- 상대 경로 누락: 전체 참조 검색과 렌더·Job 테스트로 확인한다.
- 사용자 미커밋 작업: 작업트리 파일을 그대로 이동하고 index는 변경하지 않는다.

## 진행 기록
- 2026-09-15: 역할별 이동 계획 수립.
- 2026-09-15: server/oidc/claims로 이동. Kustomize와 render.sh, 현재 실행 안내·테스트 참조 수정.
- 2026-09-15: 이동 전후 Kustomize 출력과 전달 YAML 두 파일 바이트 동일. 환경설정 테스트 33개, 배포·라우팅 회귀 13개 통과. 기존 평면 경로를 가정한 테스트는 실제 ConfigMap의 평면 마운트 디렉터리를 재현하도록 수정.
- 2026-09-15: Keycloak 원본 검사·Bash 구문·문서 링크·diff 공백 검사 통과. 실제 서버 적용·로그인 검증은 하지 않음.
