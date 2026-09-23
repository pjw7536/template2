# ExecPlan: Keycloak 전달 YAML의 운영 Traefik 구성 유지

## 목표
- 전달 YAML에 현재 운영 중인 Traefik 2개 replica, RollingUpdate, Headlamp 감시, ingress label 배치를 반영한다.

## 현재 상태
- 전달 YAML은 단독 배포 원본을 그대로 렌더하여 운영 설정을 되돌린다.
- keycloak-up은 기존 단독 원본의 hostname을 worker 검사에 사용한다.

## 범위
- 전달용 Kustomize 구성, 렌더 스크립트, 생성 YAML, 관련 안내를 수정한다.
- 공용 ingress 원본과 클러스터는 변경하지 않는다.

## 설계
- export가 형제 k8s의 Keycloak 원본을 참조하고 Traefik Deployment만 JSON patch로 변경한다.
- 기존 Headlamp RBAC를 전제로 하며 권한·DB·env 계약은 변경하지 않는다.

## 실행 단계
- [x] 전달용 구성 추가와 렌더 경로 변경
- [x] YAML 재생성과 안내 수정
- [x] 렌더 및 변경 범위 검증

## 검증
- make k8s-export
- make server-check APP=keycloak PROFILE=prod
- 생성 전후 YAML 객체를 비교하여 Traefik의 요청한 네 항목만 변경되었는지 검사
- git diff --check

## 위험과 대응
- 위험: 공용 원본 변경 시 기존 앱별 배포 검사와 다른 소비자에 영향이 발생한다.
- 대응: 전달 전용 구성으로 분리한다. 실제 서버의 RBAC·노드·VIP 상태는 사용자가 제공한 diff 외에는 확인하지 못했다.

## 진행 기록
- 2026-09-23: 공용 원본을 보존하고 전달 YAML만 운영 설정으로 생성하기로 결정했다.
- 2026-09-23: 하위 폴더에서 부모 Kustomize를 참조하면 순환으로 거부되어 형제 export 폴더를 사용했다. 이후 make k8s-export와 Keycloak 정적 검사를 통과했다.
- 2026-09-23: YAML 객체 비교로 요청한 Traefik 네 항목만 변경되었고 기본 원본이 유지됨을 확인했다. 서버 선택 checkout 테스트 17개와 git diff --check를 통과했다. 실제 클러스터에는 접속하거나 적용하지 않았다.
