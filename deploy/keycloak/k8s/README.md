# Keycloak Kubernetes 원본

파일은 역할별로 나누며, 기본 배포 진입점은 이 폴더의 `kustomization.yaml`입니다.

```text
k8s/
├── kustomization.yaml
├── server/
│   ├── stack.yaml                   # Keycloak·PostgreSQL·스토리지·Ingress
│   └── etch-realm.json               # 빈 DB의 초기 realm
├── oidc/
│   ├── oidc-setup-job.yaml           # 사내 OIDC 연결 등록 작업
│   ├── setup-oidc.sh                 # OIDC 등록 로직
│   └── admin-common.sh               # OIDC·앱 client 등록의 관리자 공통 함수
└── claims/
    ├── claim-mappers-job.yaml        # 사용자 속성 매핑 등록 작업
    ├── sync-oidc-claim-mappers.sh     # 매핑 등록 로직
    └── account-user-profile.json     # 사용자 프로필 정의
```

## 적용 순서

1. [배포 안내](../README.md)에 따라 env·인증서·worker 디스크를 준비합니다.
2. `make keycloak-check KUBE_CONTEXT=실제컨텍스트명`으로 검사합니다.
3. `make keycloak-up KUBE_CONTEXT=실제컨텍스트명`으로 기본 스택을 적용합니다.
4. 사내 OIDC 입력을 Secret에 등록하고 `oidc/oidc-setup-job.yaml`을 별도로 실행합니다.
5. `claims/claim-mappers-job.yaml`을 별도로 실행합니다.

Job 등록·재실행 명령은 [배포 안내](../README.md)의 6~7절을 따릅니다.
`make keycloak-up`은 Job을 실행하지 않습니다. Job이 나중에 사용할 스크립트·프로필은
기본 배포 때 ConfigMap으로 준비하므로 세 하위 폴더를 함께 전달해야 합니다.

## 경로와 데이터 유지

- `server/stack.yaml`만 직접 적용하지 않고 루트 Kustomize를 사용하는 앱 배포 명령을 사용합니다.
- 원본 폴더만 분리했으며 ConfigMap의 파일명과 `/opt/keycloak-config` 마운트 경로는 유지합니다.
- Job 이름·namespace·Secret·PV/PVC 이름은 유지합니다. 폴더 정리를 이유로 리소스를 삭제하지 않습니다.
- 초기 realm 파일은 빈 DB에서만 사용합니다. 일반 배포에 DB 초기화는 포함되지 않습니다.
- 전달 YAML은 `../export/`의 Traefik 운영 설정을 사용하는 `make k8s-export`로 생성합니다. `rendered/` 파일은 직접 편집하지 않습니다.
