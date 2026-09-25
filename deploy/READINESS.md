# 배포 준비 상태와 점검 결과

[배포 문서 안내](README.md)

2026-09-23 작업공간 기준 점검입니다. 운영 서버에 접속하거나 배포하지 않았습니다.
**현재 원본의 정적 검사는 통과하지만 전체 앱을 그대로 운영 배포할 준비가 끝난 상태는 아닙니다.**
이 문서는 현재 점검 기록이며 이후 운영값·서버 상태가 바뀌면 다시 검사합니다.

## 앱별 상태

| 앱 | 실제 env 검사 | 남은 준비 |
| --- | --- | --- |
| Keycloak | 통과 | 서버의 기존 비밀번호와 일치 확인, TLS 인증서·개인키, worker 디스크·이미지 접근·DNS/VIP 검증 |
| Airflow | 실패 | NODE_NAME, DAG 포함 이미지 주소·태그 확인, 관리자 이메일, DB·관리자 비밀번호·Fernet 키·웹서버 키·Portal 연동 토큰 |
| Headlamp | 통과 | TLS·CA, Keycloak client·그룹과 Client Secret, 모든 API server의 OIDC 인증 설정 |
| Monitoring | 실패 | NODE_NAME, registry.k8s.io 사내 미러, Grafana Secret, 노드 디스크·기존 Operator 확인 |
| Portal | API/Web/MinIO 실패 | 공개 주소, 외부 DB, Django·연동 credential, API/Web 이미지, 업무 데이터 PVC·MinIO 저장소 |
| FTP | env 파일 방식 아님 | 대상 노드 라벨·저장소·계정 Secret·이미지 반입·방화벽·passive 송수신 검증 |

실제 env 검사에서 첫 오류가 나오면 이후 오류가 가려질 수 있습니다. 위 표는 파일 조사도 포함합니다.
Airflow의 이미지 태그 형식이 유효해도 해당 이미지가 registry에 있고 필요한 DAG·초기화 코드가 들어 있는지는 별도 확인해야 합니다.
Portal 기본 업무 볼륨은 `emptyDir`이므로 운영 데이터 저장소 준비 없이 업무 기능을 사용하지 않습니다.

## 이번 점검에서 수정한 부분

- Keycloak: Ready 노드라도 cordon·NoSchedule/NoExecute taint가 있으면 Secret·배포 변경 전에 중단합니다.
- Airflow: 클러스터 버전·노드·기존 DB 비밀번호/Fernet 키 검사를 공용 라우팅 변경보다 먼저 수행합니다.
  Ingress 없는 `airflow-check`도 이 검사를 수행합니다.
- Airflow: 기존 내부 DB PVC가 있는데 비밀번호 Secret이 사라졌으면 기존 비밀번호로 복원하도록 중단합니다.
- Airflow 백업: Fernet 키를 포함하는 통합 `k8s.env` 전체를 백업합니다.
- Headlamp: 아직 Headlamp가 설치되지 않은 서버에서도 따라갈 수 있도록 최초 설치 순서를 명시했습니다.
- Portal: 가이드·운영 overlay의 오래된 단일 env/비밀값 위치 설명을 단일 env 계약에 맞췄습니다.

## 새 서버에서 필요한 파일과 외부 준비

일반 `.env`와 Kubernetes 원본은 Git으로 전달합니다. 배포에는 `deploy/`와 루트 `Makefile`이 필요합니다.
`local/`은 필요 없습니다. Airflow 최종 이미지를 서버에서 빌드할 때만 `apps/airflow/`를 추가합니다.

다음 입력은 Git으로 전달되지 않으므로 별도로 준비합니다.

- [사이트별 인증서](shared/certs/README.md): Keycloak·업무 도메인의 fullchain과 개인키, 사내 Root/Issuing CA
- Airflow·Headlamp·Monitoring의 고정 Helm chart와 해당 이미지의 사내 접근 경로
- kubeconfig·배포 권한, Python·kubectl·Helm·Bash·OpenSSL, DNS/VIP·방화벽·worker 디스크

현재 작업공간의 인증서 폴더에는 실제 인증서가 없습니다. 실제 서버에 이미 넣었다면 서버에서 검사합니다.
env 파일이 존재해도 `replace-me` 등의 임시값이면 준비 완료가 아닙니다.
기존 분리 구성을 사용한 서버는 최신 통합 env에 기존 값이 보존됐는지 확인합니다.

## 검사 수준을 구분하기

1. **원본 검사:** 추적 env 형식·Kustomize·Helm 렌더 검증. 실제 운영값·이미지 pull·로그인 성공은 확인하지 않습니다.

   ```bash
   make server-check APP=all PROFILE=prod
   ```

2. **실제 env 검사:** 비밀번호·토큰이 포함된 앱별 env를 검사합니다. Helm 앱은 고정 chart도 필요합니다.

   ```bash
   make env-check APP=keycloak PROFILE=prod COMPONENT=server
   make env-check APP=airflow PROFILE=prod COMPONENT=server
   make env-check APP=headlamp PROFILE=prod COMPONENT=server
   ```

3. **대상 클러스터 검사:** env 검사를 해결한 뒤 대상 context를 지정합니다. 아래 두 명령은 적용하지 않습니다.

   ```bash
   read -r -p '운영 Kubernetes context: ' KUBE_CONTEXT
   make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT"
   make airflow-check KUBE_CONTEXT="$KUBE_CONTEXT"
   ```

   `headlamp-check`는 env·렌더 검사입니다. Secret·CA·TLS·Traefik 검사는 `headlamp-up`의 적용 전 단계에서 수행하며,
   OIDC 로그인과 그룹별 권한까지 자동으로 검증하지는 않습니다.
   이미지 pull 권한, 디스크 존재·용량, 사용자 정의 taint/toleration, 실제 DNS/TLS·방화벽은 서버에서 확인합니다.

4. **실제 기능 검증:** [접속·기능 검증](shared/docs/kubernetes/06-verification.md)에 따라 실행합니다.
   Headlamp는 [OIDC 가이드](headlamp/OIDC.md)의 모든 API server 설정과 그룹별 허용/거부 테스트가 필요합니다.
   Airflow는 health의 DB·scheduler 상태, 관리자 로그인, DAG·로그 및 필요 시 Portal 연동까지 확인합니다.

## 적용 순서와 복구

1. Keycloak 비밀값·인증서·디스크 준비 → `keycloak-check` → `keycloak-up` → HTTPS·로그인 확인.
2. Airflow 이미지·chart·비밀값·디스크 준비 → `airflow-check` → `airflow-up` → health·DAG 확인.
3. Headlamp chart·TLS·Keycloak client·CA·API server OIDC 준비 → `headlamp-check` → `headlamp-up` → 그룹별 로그인 확인.

Airflow 자체 로그인은 현재 관리자 계정 방식입니다. Keycloak 로그인을 사용하는 앱은 Headlamp이며,
Airflow까지 SSO로 전환하는 구성은 포함되지 않습니다.
Headlamp와 HTTPS Airflow는 기존 공용 Traefik이 필요합니다. Ingress 없는 Airflow는 독립 배포할 수 있습니다.

업데이트 전 DB·비밀값·이미지/chart 버전·인증서를 백업합니다. 통합 env 전체를 백업해야 credential과 Fernet 키를 복구할 수 있습니다.
DB migration 뒤 Helm rollback만으로 DB가 이전 상태로 돌아가지는 않습니다.
Keycloak·Airflow는 단일 worker·local PV 구성으로 자동 HA가 아니며 실제 복원 훈련은 아직 검증하지 않았습니다.

## 이번 검증의 범위와 남은 한계

- 전체 6개 앱 정적·렌더 검사, 관련 배포 회귀 검사, env 병합·Git 경계, 문서 링크·셸 문법을 점검했습니다.
- 사내 이미지 registry, API server 설정, worker의 파일·권한·포트는 접근할 수 없어 검증하지 못했습니다.
- 사용자 정책에 따라 env의 credential도 private Git 저장소에서 관리하며 인증서·개인키 파일은 제외합니다.
  과거 예시의 비밀번호를 실제로 사용했다면 사용 여부를 확인하고 별도 교체 절차를 수행해야 합니다.
- 운영 배포 완료 여부는 [검증 결과 기록 형식](shared/docs/kubernetes/06-verification.md)에 따라 서버에서 기록합니다.
