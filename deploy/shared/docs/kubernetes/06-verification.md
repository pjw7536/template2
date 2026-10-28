# 06. 접속·기능 검증

[가이드 홈](README.md) · 이전: [배포](05-applications.md) · 다음: [운영](07-operations.md)

클러스터 상태 → Worker 직접 접속 → VIP → DNS → 실제 기능 순서로 확인합니다.
배포하지 않은 앱은 `미배포`로 기록합니다.

## 1. 리소스 확인 — CP1

01장 또는 04장에서 `KUBE_CONTEXT`를 지정한 터미널에서 실행합니다.

```bash
read -r -p '확인할 앱 namespace: ' APP_NAMESPACE
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get deployment,statefulset,daemonset
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get jobs,pvc
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get service,ingress,endpointslices
```

다음 상태를 모두 확인합니다.

- 필요한 replica 수가 준비되고 Pod의 READY가 충족됩니다.
- PVC는 Bound, 일회성 Job은 Completed 상태입니다.
- Service에 준비된 endpoint가 있습니다.

Pod가 Running이라는 이유만으로 앱이 준비됐다고 판단하지 않습니다.

## 2. HTTPS 확인 — 접근 가능한 PC

APP VIP를 사용하는 앱의 정상 health 경로로 확인합니다.
Portal은 `/api/v1/health/`, Airflow는 `/airflow/health`입니다.

```bash
read -r -p '앱 인증서 도메인: ' APP_HOST
read -r -p 'health 경로(/로 시작): ' APP_HEALTH_PATH
read -r -p '확인할 Worker 또는 VIP IP: ' TARGET_IP
read -r -p '신뢰할 CA PEM 파일 절대 경로: ' CA_FILE
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" --resolve "$APP_HOST:443:$TARGET_IP" \
  "https://$APP_HOST$APP_HEALTH_PATH"
```

같은 도메인·경로로 `TARGET_IP`를 각 backend → APP VIP 순서로 바꿔 실행합니다.
마지막에는 DNS도 확인합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" "https://$APP_HOST$APP_HEALTH_PATH"
```

OS가 해당 CA를 신뢰하면 `--cacert`를 생략할 수 있습니다.
인증서 검증을 건너뛰는 `-k`는 사용하지 않습니다.

**성공 기준:** TLS 검증을 통과하고 health 응답 내용이 정상이어야 합니다.
Airflow는 HTTP 200 외에 DB와 scheduler가 healthy인지도 확인합니다.
Keycloak은 [VIP 문서](../../ingress/VIP.md)의 도메인 검사와 아래 로그인 검증을 수행합니다.

## 3. 실제 기능 확인

| 앱 | 시나리오 |
| --- | --- |
| Keycloak | HTTPS → 사내 OIDC 로그인 → realm·사용자 claim |
| Portal | 로그인 callback → API → 로그아웃, 시험 파일 업로드·다운로드 |
| Airflow | UI 로그인·health, Portal 연동 시 시험 DAG 트리거·결과 |
| Monitoring / Headlamp | Grafana 지표·target / Keycloak 로그인·그룹별 리소스 조회 |
| FTP | 노드 passive 접속·시험 파일 송수신·저장 위치 |

시험 데이터는 정상 삭제 절차로 정리합니다.
결과에는 수행일·담당자, context·namespace, 커밋·이미지·chart 버전을 남깁니다.
정적 검사, 리소스 상태, 접속·기능 검증의 결과를 나누어 적고 미완료 항목과 다음 조치를 덧붙입니다.
비밀값은 기록하지 않습니다. 접근하지 못했거나 확인 대기 중인 항목은 성공으로 표시하지 않습니다.
