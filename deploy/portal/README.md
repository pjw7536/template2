# Portal 배포·환경설정

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

사내 Kubernetes의 Portal 환경설정은 **`env/prod/`**에 작성합니다.
이미지·Ingress·영속 저장소 placeholder는 [운영 overlay](k8s/overlays/prod/README.md)에서도 실제 값으로 준비합니다.
현재 운영 중인 Keycloak 설정은 `../keycloak/env/prod.env`에 그대로 둡니다.
환경설정은 `env/`, CI 정의는 `compose/test.yml`, Kubernetes와 프록시 정의는 `k8s/`에서 관리합니다. 로컬 개발 설정과 실행 도구는
저장소 루트의 [local/](../../local/README.md)에 있습니다.
env 작성만으로 앱이 배포되지는 않습니다.

서버에서는 `make server-check APP=portal`로 local 없이 원본을 검사합니다.

## 어떤 파일을 수정하나요?

| 파일 | 넣는 내용 | 넣지 않는 내용 |
| --- | --- | --- |
| `env/prod/api.env` | Portal 서버, DB 주소, Keycloak 로그인, 업무 연동 주소 | 비밀번호·토큰·인증 헤더는 `api.env`에 저장 |
| `env/prod/web.env` | 브라우저에서 사용할 Portal·API·파일 주소와 화면 링크 | 비밀번호와 token 등 비밀값 |
| `env/prod/minio.env` | MinIO 공개 주소 | 계정·비밀번호·접근 키는 `minio.env`에 저장 |

API는 Django 업무 기능들이 함께 실행되는 하나의 서버입니다. Assistant·Emails·Drone을
별도 env 파일로 쪼개서 합성하지 않고 `api.env` 안의 기능별 구역으로 관리합니다.
Airflow 서버 자체의 설정은 `../airflow/env/`, API에서 Airflow에 연결하는 설정은 `api.env`에 둡니다.

| 환경 폴더 | 사용처 |
| --- | --- |
| `env/prod/` | 사내 Kubernetes 운영 Portal |
| `local/portal/env/` | 외부망에서도 실행 가능한 Kubernetes 개발 입력 |
| `local/portal/env/api-k8s.env` | 로컬 Kubernetes에서만 적용하는 API 차이. 단독 사용하지 않음 |
| `env/test/` | API 자동 테스트 |

환경끼리 자동 상속하지 않습니다. 로컬 Kubernetes만 `local/portal/env/api.env`에
`local/portal/env/api-k8s.env`를 덮어쓰고 `local/portal/env/minio.env`의 API 접근 키를 선택해 합성합니다.

`internal/`은 `env/prod/`로 통합했습니다. 이 작업 공간의 기존 Compose 입력은
`env/prod/api.env.pre-k8s.bak`, `env/prod/web.env.pre-k8s.bak`, `env/prod/minio.env.pre-k8s.bak`에
복구용으로 보존했습니다. 사본은 Git 제외이며 배포 도구가 자동으로 읽지 않습니다.
새 prod API는 준비한 Keycloak 입력과 기존 업무 연동값을 사용합니다. DNS·DB 미입력과
이전 Compose 전용 업무 주소는 실제 배포 전에 확인합니다. 배포 시점의 env 버전을 함께 기록합니다.

사내 서버는 Kubernetes로 배포합니다.

## 사내 배포 입력 순서

저장소 루트에서 시작합니다. Git에서 받은 env의 서버별 값을 확인합니다.

```bash
# Git에서 받은 운영 env의 접근 권한을 설정합니다.
chmod 600 deploy/portal/env/prod/api.env deploy/portal/env/prod/web.env deploy/portal/env/prod/minio.env
```

1. `api.env`의 **1~4번 구역**에 Portal DNS, DB, 로그인, HTTPS 설정을 작성합니다.
   DB 비밀번호·Django Secret Key·OIDC Client Secret은 `api.env`에 저장합니다.
   Portal DB는 Keycloak 전용 DB와 별개입니다. `<Portal DNS>`는 실제 Portal 주소로 바꿉니다.
2. `web.env`에 같은 Portal 공개 주소와 파일 접근 주소를 작성합니다.
3. `minio.env`에 실제 사용할 계정을 작성합니다. 접근 계정이 MinIO에 존재하고 필요한
   bucket 권한을 갖도록 별도 준비해야 합니다. env에 이름을 적는 것만으로 계정이 생성되지는 않습니다.
4. 업무 기능을 연결할 때 `api.env`에 해당 구역을 추가합니다.
   비밀번호·토큰·인증 헤더는 같은 `api.env`에 입력합니다.
   [전체 설정 설명](../../docs/configuration.md)을 보고 필요한 값만 입력합니다.
   기존 다른 환경 파일을 통째로 복사하면 dummy 주소나 다른 환경의 계정까지 가져올 수 있습니다.

API 파일의 구역 번호는 모든 환경에서 같습니다. 설정이 없는 구역은 생략되므로
`env/prod/api.env`에 모든 번호가 보이지 않아도 정상입니다. 기존 profile의 timeout,
cache, 빈 값은 동작 보존을 위해 유지했습니다. 빈 값과 변수 생략은 의미가 다를 수 있습니다.

## 서로 맞춰야 하는 값

| 기준 | 함께 확인할 항목 |
| --- | --- |
| Portal 공개 주소 | API의 `FRONTEND_BASE_URL`, CORS·CSRF 주소, Web의 `VITE_SITE_URL`, Ingress host·TLS |
| Portal API 주소 | `PUBLIC_API_BASE_URL`은 `/api/v1` 포함, Web의 `VITE_BACKEND_URL`은 Portal origin 사용 |
| Portal 로그인 | `OIDC_REDIRECT_URI`와 Keycloak Portal client의 허용 callback |
| Portal client 계정 | API의 `OIDC_CLIENT_ID`·`OIDC_CLIENT_SECRET`과 Keycloak에 등록한 Portal client |
| 파일 저장소 계정 | API의 `MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`와 실제 MinIO 접근 계정 |

사내 Kubernetes의 API Secret은 `api.env`만 읽습니다. 파일 기능을 사용할 때는
`MINIO_ENDPOINT=http://minio:9000` 및 필요한 접근 키를 `api.env`에도 명시합니다.
`minio.env`가 API에 자동으로 합쳐지는 것은 로컬 Kubernetes 경로뿐입니다.
업무 기능에서 요구하는 bucket과 권한도 별도로 준비합니다.

`OIDC_PROVIDER=keycloak`일 때도 현재 코드의 호환 변수명인 `ADFS_AUTH_URL`과
`ADFS_LOGOUT_URL`을 사용합니다. 이름만 보고 사내 ADFS 주소로 바꾸지 않습니다.
Portal client secret과 사내 OIDC client secret은 서로 다른 값입니다.

Web의 `VITE_*`, `BACKEND_API_URL`, `BACKEND_URL`, `MINIO_ENDPOINT`는
브라우저 설정에 공개됩니다. `BACKEND_API_URL`도 비밀 서버 전용 주소가 아니라
브라우저 API 주소의 fallback으로 쓰이므로, 새 설정에는 브라우저에서 접근 가능한 주소를 넣습니다.

현재 Portal 프록시는 `/minio/`를 파일 API로 전달하지만 MinIO 관리 콘솔은 노출하지 않습니다.
`MINIO_BROWSER_REDIRECT_URL`은 콘솔을 별도로 노출한 뒤 그 주소를 넣습니다.
`MINIO_SERVER_URL`과 Web의 `VITE_MINIO_ENDPOINT`는 실제 파일 공개 경로에 맞추고,
별도 bucket 권한 및 업로드·다운로드 동작도 확인합니다.

## 검사와 적용

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make env-check APP=portal PROFILE=prod COMPONENT=web
make env-check APP=portal PROFILE=prod COMPONENT=minio
make env-check APP=portal PROFILE=prod COMPONENT=client
```

필수값이 비어 있거나 임시값이면 배포 전 검사가 실패합니다.
검사 통과는 필수 입력 확인이며 DB 접속이나 로그인 성공을 보장하지 않습니다.
`make prod-profile-env-check`는 같은 운영 API 검사를 실행합니다. Airflow·RAG 등 선택 업무
연동을 필수로 강제하지 않으므로 해당 기능을 사용할 때는 endpoint와 계정을 별도로 확인합니다.
prod Web의 API 주소는 브라우저에서 접근 가능한 전체 origin URL로 작성합니다.

Namespace와 배포 리소스 준비 후 필요한 Secret만 등록합니다.

```bash
make k8s-env APP=portal PROFILE=prod COMPONENT=api
make k8s-env APP=portal PROFILE=prod COMPONENT=web
make k8s-env APP=portal PROFILE=prod COMPONENT=minio
```

Secret 등록은 실행 중인 Pod를 자동 재시작하지 않습니다. Portal client 등록은
별도 입력 등록과 Job 실행이 필요합니다. [운영 overlay 배포 순서](k8s/overlays/prod/README.md)와
[client 등록 안내](k8s/jobs/keycloak-client/README.md)를 따릅니다.

`env/prod/api.env`, `web.env`, `minio.env`는 credential을 포함해 Git에서 관리합니다.
비밀번호·토큰·인증 헤더는 각각 `api.env`, `minio.env`에 함께 저장합니다.
공용 검사·Secret 등록 도구는 지정한 env 하나를 읽습니다. `*.pre-k8s.bak`와 인증서·개인키 파일은 Git에서 제외됩니다.
env는 clone으로 전달됩니다. 인증서·개인키 파일은 CP1에 별도로 준비합니다.
