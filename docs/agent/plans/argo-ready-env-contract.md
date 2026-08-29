# ExecPlan: Argo CD 준비형 profile 독립 env 계약

## 목표
- 현재 env를 profile별 Kubernetes ConfigMap과 Secret으로 바로 옮길 수 있는 독립 구조로 정리한다.
- prod Web의 `VITE_*` 설정을 이미지 빌드가 아닌 컨테이너 시작 시 주입한다.
- local/OIDC/prod/test의 현재 최종 환경값과 offsite dummy 동작을 보존한다.

## 변경 전 상태
- env 파일은 root `env/`에 profile과 서비스 기준이 혼재되어 있었다.
- API server profile은 config와 credential을 한 파일에서 함께 관리했다.
- prod Web의 `VITE_*`는 Docker build arg를 거쳐 정적 번들에 포함됐다.
- 배포는 Docker Compose 기반이며 Kubernetes/Argo CD manifest는 없다.

## 범위
- 수정: `env/`, Compose, Makefile, env 검증 스크립트와 문서, Web runtime config 로딩부와 Docker 실행 계약.
- 유지: 실제 env 값, API/DB/auth endpoint 계약, local dummy 서비스, 기존 Docker Compose 실행 진입점.
- 제외: Kubernetes/Helm/Kustomize/Argo CD manifest와 cluster 배포.

## 설계
- 모든 비민감 설정은 `env/overlays/<profile>/<service>.config.env`에 완결해서 둔다.
- credential/token/password/header는 `env/overlays/<profile>/<service>.secret.env`에 둔다.
- Compose는 config 파일 다음 secret 파일을 읽어 Secret이 최종 override가 되게 한다.
- Web runner는 시작 시 허용된 runtime key만 `runtime-env.js`로 생성한다.
- Web 코드의 공통 env reader는 runtime config를 우선하고 Vite env를 개발 fallback으로 사용한다.

## 실행 단계
- [x] 기존 env key와 최종 profile 값을 snapshot으로 확인한다.
- [x] env 파일을 profile별 독립 config/secret 구조로 재배치한다.
- [x] Compose, Makefile, 검증 스크립트, 문서 참조를 새 경로로 변경한다.
- [x] Web runtime config 생성기와 공통 reader를 추가하고 소비부를 전환한다.
- [x] profile별 최종 값 동등성과 dev/OIDC/prod/test 검증을 실행한다.
- [x] local/OIDC/prod/test가 최종 변수 전체를 독립 소유하도록 정리한다.

## 검증
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.test.yml config --quiet`
- profile별 Compose environment key/value hash 비교
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:docs`
- Web 관련 단위 테스트
- `git diff --check`

## 위험과 대응
- 위험: env 이동 중 key 또는 override 순서가 바뀔 수 있다.
- 대응: 변경 전후 profile별 최종 environment를 민감값 비노출 hash로 비교한다.
- 위험: runtime config 전환으로 dev fallback이 깨질 수 있다.
- 대응: 빈 runtime config에서는 기존 `import.meta.env`를 읽도록 유지하고 Web 테스트를 실행한다.
- 위험: secret 분류로 API와 Airflow shared token이 어긋날 수 있다.
- 대응: profile 검증에서 token 일치를 새 secret 경로 기준으로 확인한다.

## 진행 기록
- 2026-08-29: 사용자 결정에 따라 Web runtime config와 profile별 config/secret 재구성을 함께 진행하기로 했다.
- 2026-08-29: dev/OIDC/prod/test Compose의 최종 environment hash가 재구성 전과 일치함을 확인했다.
- 2026-08-29: Web runtime env 생성기·reader·no-cache 경로를 추가하고 기존 Vite build arg를 제거했다.
- 2026-08-29: Compose, 문서, frontend boundary, agent test, skill validator, Web runtime 단위 테스트·빌드·lint를 통과했다.
- 2026-08-29: 전체 Web 테스트 204개 assertion은 통과했으나 기존 Assistant hook suite 종료 시 비동기 `window is not defined` 오류가 1건 발생했다. 해당 테스트 단독 실행 21개는 통과했다.
- 2026-08-29: OIDC/prod profile 검증은 서버 입력 전인 OIDC/ADFS 필수값이 비어 있어 의도대로 실패하는 것을 확인했다.
- 2026-08-29: profile별 Airflow·Monitoring Compose override를 추가하고 같은 profile의 API/Airflow token을 비교하도록 서버 검증을 변경했다.
- 2026-08-29: profile 간 상속 없이 각 profile이 전체 설정을 소유하며 OIDC/prod key 구성을 검증하도록 최종 정리했다.
- 2026-08-29: 최종 dev/OIDC/prod/test environment hash가 최초 snapshot과 일치하며 Compose, 문서, agent test, skill 검증을 통과했다.
