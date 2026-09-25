# Headlamp HTTPS 적용

[운영 안내](README.md) · [인증서 추출·검증·적용](../shared/certs/README.md)

| 항목 | 운영값 |
| --- | --- |
| 접속 주소 | `https://etch.samsungds.net/headlamp/` |
| 인증서 폴더 | `deploy/shared/certs/etch.samsungds.net/` |
| 인증서·개인키 | `fullchain.crt`, `private.key` |
| TLS Secret | `headlamp/headlamp-tls` |
| 공용 CA 폴더 | `deploy/shared/certs/ca/` |

## 1. 인증서 준비·등록

[공용 인증서 안내](../shared/certs/README.md)의 **Headlamp 사이트 선택**을 사용합니다.
PFX·P7B 추출, 기존 파일 검증, TLS Secret 등록·갱신, 실제 제공 인증서 확인은 그 안내를 따릅니다.
이미 HTTPS가 정상이라면 인증서를 다시 추출하거나 재등록하지 않습니다.

## 2. 로그인 준비

[Keycloak 로그인 가이드](OIDC.md)를 따라 client·그룹·Secret·CA·API server 인증을 준비합니다.
Headlamp HTTPS 인증서와 Keycloak을 신뢰하는 CA는 별도입니다.

기본 env에는 운영 도메인·TLS Secret·Keycloak issuer·OIDC Secret·CA 이름이 들어 있습니다.
실제 `env/k8s.env`가 있으면 그 파일이 우선하므로 이전 값이 남았는지 확인합니다.

## 3. 검사·적용

CP1의 저장소 루트에서 context를 명시하고 실행합니다.

```bash
kubectl config get-contexts
read -r -p '대상 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
make server-check APP=headlamp PROFILE=prod
make headlamp-check
make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"
make headlamp-ui KUBE_CONTEXT="$KUBE_CONTEXT"
```

앞 명령이 실패하면 해결한 뒤 다음 명령을 실행합니다.
Headlamp는 `/headlamp` baseURL로 실행하고 기존 Traefik 감시 범위를 보존하며 namespace를 추가합니다.
`StripPrefix`를 적용하지 않습니다. 공용 Traefik 원본 전체를 덮어쓰지 않습니다.

## 4. 확인

브라우저에서 위 HTTPS 주소를 열고 Keycloak으로 로그인합니다.
인증서 체인은 공용 안내의 실제 HTTPS 검사를 사용하고,
로그인·그룹별 권한 검사는 [OIDC 가이드](OIDC.md)를 따릅니다.
인증서가 정상인데 404라면 Ingress 경로·감시 namespace, 503이면 Service와 Pod 상태를 확인합니다.
PC만 신뢰 오류가 나면 [Keycloak TLS의 클라이언트 신뢰 안내](../keycloak/03_TLS.md)를 참고합니다.
