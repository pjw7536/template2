# 08. Keycloak Kubernetes 원본 안내

[시작 안내](../README.md) · 실행: [서버 설치](../01_SERVER_SETUP.md) / [0~5단계 설정](../04_SETUP_FLOW.md)

이 문서는 manifest·스크립트·전달 YAML을 유지보수할 때 사용합니다.
운영 명령은 위의 실행 문서를 따릅니다. 서버 스택과 설정 Job은 별도 작업입니다.

## 파일 구조

```text
k8s/
├── kustomization.yaml                # 서버·공용 ingress·관리 ConfigMap 묶음
├── server/
│   ├── stack.yaml                    # PostgreSQL·Keycloak·PV/PVC·서비스
│   └── etch-realm.json                # 신규 etch realm 기본값
├── oidc/
│   ├── oidc-setup-job.yaml            # 사내 IdP Job, Realm Job 생성 시에도 재사용
│   ├── setup-realm.sh                # 기존 realm은 보존, 없을 때만 생성
│   ├── setup-oidc.sh                  # 해석된 endpoint로 IdP 생성/갱신
│   └── admin-common.sh               # 관리 CLI·문자열 처리 공통 함수
└── claims/
    ├── claim-mappers-job.yaml         # 프로필+IdP mapper 통합 Job 원본
    ├── sync-oidc-claim-mappers.sh      # 전용 모드와 통합 모드 지원
    ├── account-user-profile.json      # User Profile 정의
    └── sdwt-access-scope.json         # SDWT groups 공통 scope 정의
```

Traefik 원본은 `deploy/shared/ingress`에서 참조합니다.

## 서버와 설정 Job의 차이

| 실행 | 동작 |
| --- | --- |
| `keycloak-up` | 서버 스택·관리 ConfigMap 준비. 설정 Job은 실행하지 않음 |
| 0번 Realm | IdP Job 원본에서 OIDC Secret 의존성을 제거하고 realm 생성 스크립트 실행 |
| 1번 IdP | Discovery 해석 결과를 Secret으로 전달한 뒤 IdP Job 실행 |
| 2번 User Profile | claim Job 원본에 `KEYCLOAK_PROFILE_ONLY=true`를 넣어 실행 |
| 3번 IdP mapper | claim Job 원본에 `KEYCLOAK_SKIP_PROFILE=true`, 대상 `idp`로 실행 |
| 4번 Portal | Portal 소유 Job·ConfigMap 사용 |
| 기존 통합 실행 | IdP Job 이후 기본 claim Job으로 프로필·mapper를 함께 실행 |

단계별 0~4번은 최신 공통 관리 ConfigMap을 준비합니다.
파생 Job은 이미지·볼륨·리소스·보안 설정을 기존 manifest에서 재사용하며 Job 이름을 단계별로 구분합니다.
Job 이름과 실패 로그 조회는 [완료 확인](../04_SETUP_FLOW.md#완료-확인과-실패-재실행)에 있습니다.

`setup-oidc.sh` 자체는 discovery를 조회하지 않습니다. 실행 호스트가 먼저 endpoint를 해석해야 합니다.
`claim-mappers-job.yaml`을 직접 실행하면 기본적으로 프로필과 IdP mapper가 **둘 다** 변경됩니다.
각각 실행하려면 2번·3번 명령을 사용합니다.

## 생성 파일 갱신

원본을 변경한 뒤 저장소 루트에서 실행합니다. 아래 명령은 클러스터에 적용하지 않습니다.

```bash
make k8s-export
make server-check APP=keycloak PROFILE=prod
```

| 생성 파일 | 포함 내용 | 사용 조건 |
| --- | --- | --- |
| `rendered/internal-keycloak-stack.yaml` | 서버·공통 ConfigMap·운영 Traefik 설정 | [서버 문서](../01_SERVER_SETUP.md)의 수동 전달 배포 조건 확인 |
| `rendered/internal-keycloak-claim-mappers.yaml` | 관리 ConfigMap + 통합 claim Job | IdP가 이미 있고 프로필·mapper를 함께 갱신할 때 |

`rendered/`는 직접 편집하지 않습니다. 원본 `k8s/`, `export/`, `scripts/render.sh`에서 갱신합니다.
전달 YAML만으로 discovery나 독립 단계 실행 파일 전체를 대체할 수는 없습니다.

## 유지해야 하는 계약

- 서버 배포는 `stack.yaml` 단독 적용보다 공용 라우팅을 보존하는 앱 배포 도구를 사용합니다.
- 공통 ConfigMap 파일명과 `/opt/keycloak-config` 마운트 경로는 Job이 참조합니다.
- `etch-realm.json`은 서버 최초 import와 0번 realm 생성에 사용합니다. 기존 realm을 덮어쓰지 않습니다.
- Secret·PV/PVC 이름은 기존 데이터를 연결하므로 폴더 정리를 이유로 삭제·변경하지 않습니다.
- 운영 전달 스택의 Traefik 배치·감시 범위는 기본 스택과 다릅니다. 상세 조건은 [서버 설치](../01_SERVER_SETUP.md)에 있습니다.
