# ExecPlan: Grist Grouped View 커스텀 위젯

## 목표
- Work Hub Grist의 Custom Widget 갤러리에서 `Grouped View`를 선택할 수 있게 한다.
- 위젯 코드는 저장소에서 고정 버전으로 관리하고 외부 CDN 없이 제공한다.
- 위젯은 별도 untrusted origin에서 실행하며 Grist에는 `read table` 권한만 요청한다.

## 현재 상태
- Work Hub는 `gristlabs/grist-oss:1.7.13` 이미지를 dev/OIDC/prod Compose에서 실행한다.
- Grist 소스는 vendor하거나 fork하지 않는 경계를 유지한다.
- Grouped View upstream은 MIT로 공개된 단일 HTML 위젯이며, 확인한 revision은 `010285c27a4b368910b9ba7287091436308639c1`이다.
- upstream HTML은 Grist API와 Google Fonts를 외부 URL에서 불러오므로 그대로 사용하면 offsite 환경에서 동작이 보장되지 않는다.

## 범위
- Grist user plugin 디렉터리에 Grouped View 위젯과 manifest를 추가한다.
- dev/OIDC/prod Grist 서비스에 plugin read-only mount와 untrusted widget origin 설정을 추가한다.
- dev/운영 Nginx에 widget origin 전용 proxy와 제한적인 CSP를 추가한다.
- Work Hub 운영·환경 문서에 DNS/TLS 및 사용 절차를 기록한다.
- Grist core 이미지, Work Hub API/DB schema, Grist document schema는 변경하지 않는다.

## 설계
- `deploy/grist/plugins/work-hub-grouped-view`를 Grist의 `GRIST_USER_ROOT/plugins` 아래로 read-only mount한다.
- Grist plugin server는 container의 `8485`에서 동작하고 Nginx가 dev `http://localhost:8101`, OIDC/prod `https://<GRIST_WIDGET_HOST>`로 노출한다.
- 위젯 HTML은 plugin 경로의 `./grist-plugin-api.js`를 사용해 실행 중인 Grist와 같은 API 버전을 사용한다.
- 외부 font/CDN 호출을 제거하고 widget origin의 Nginx CSP로 임의 네트워크 전송을 차단한다.
- public API, migration, auth/permission mapping 변화는 없다. 위젯 manifest의 access level은 `read table`이다.

## 실행 단계
- [x] upstream source와 manifest 계약을 고정하고 자체 호스팅 파일을 추가한다.
- [x] dev/OIDC/prod Compose와 Nginx에 분리 origin을 연결한다.
- [x] 환경·운영 문서와 third-party 출처를 갱신한다.
- [x] 정적 검사, Compose 렌더링, 실제 Grist gallery/API 로드를 검증한다.

## 검증
- `python -m json.tool deploy/grist/plugins/work-hub-grouped-view/widgets.json`
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.oidc.yml config`
- `docker compose -f docker-compose.yml config`
- Grist test container에서 `/api/widgets`에 `Grouped View`가 포함되는지 확인한다.
- widget origin에서 HTML과 `grist-plugin-api.js`가 제공되고 CSP가 설정되는지 확인한다.

## 위험과 대응
- 위험: same-origin widget이 Grist session 권한을 우회할 수 있다.
- 대응: widget 전용 origin/port를 사용하고 Grist main origin과 분리한다.
- 위험: widget이 표 데이터를 외부로 전송할 수 있다.
- 대응: 외부 의존성을 제거하고 `connect-src 'none'` CSP를 적용한다.
- 위험: 운영 widget host의 DNS 또는 TLS SAN이 누락될 수 있다.
- 대응: `GRIST_WIDGET_PUBLIC_URL`과 `GRIST_WIDGET_HOST`를 env-driven으로 두고 배포 전제 조건을 문서화한다.

## 진행 기록
- 2026-08-05: Grist 1.7.13의 disk widget plugin과 untrusted plugin server 계약을 확인하고 분리 origin 설계를 선택했다.
- 2026-08-05: upstream revision을 고정하고 외부 runtime dependency 제거, 한국어 UI, read-only manifest를 추가했다.
- 2026-08-05: dev/OIDC/prod Compose 렌더링, dev/prod Nginx 문법, inline JavaScript 문법과 JSON을 검증했다.
- 2026-08-05: 격리된 Grist 1.7.13과 Nginx에서 `/api/widgets` 등록, widget HTML, `grist-plugin-api.js`, CSP 응답을 확인했다.
