# ExecPlan: Headlamp APP VIP HTTPS

## 목표
- 기존 Traefik으로 etch.samsungds.net/headlamp/ 접속을 지원한다.
- 인증서 발급·등록부터 배포까지 서버 작업 순서를 제공한다.

## 현재 상태
- 고정 Helm chart 0.45.0, Ingress 비활성, 조회용 토큰 로그인이다.
- APP VIP용 Traefik은 etch-sso에 존재하며 기존 배치 설정을 보존해야 한다.

## 범위
- Headlamp env·배포 도구·테스트·문서. Portal 소스는 변경하지 않는다.

## 설계
- 선택적 HEADLAMP_HOST와 HEADLAMP_TLS_SECRET 설정으로 HTTPS를 켠다.
- /headlamp baseURL과 chart의 probe 경로, Prefix Ingress를 사용한다.
- 외부에서 발급한 TLS Secret을 먼저 준비한다. 인증서 자동 발급은 하지 않는다.
- 공통 routing.py로 namespace 권한과 감시 목록만 확장한다. VIP 배치·이미지는 보존한다.
- 기존 env는 port-forward 동작을 유지한다.

## 실행 단계
- [x] env·Ingress 렌더 및 TLS 사전 검사 구현
- [x] 기존 Traefik namespace 감시 보존·권한 연결
- [x] 인증서 절차 문서화 및 회귀 검증

## 검증
- python3 -m unittest discover -s deploy/headlamp/tests
- 고정 chart 렌더로 baseURL·probe·Ingress·TLS 확인
- make server-check APP=headlamp
- node --test apps/tooling/tests/server-checkout.test.cjs
- git diff --check

## 위험과 대응
- 인증서 미준비: HTTPS 배포 전에 TLS Secret 존재·타입·필수 키를 검사한다.
- 공용 Traefik 영향: 기존 전체 spec을 재적용하지 않고 args만 동시 변경 검사와 함께 patch한다.
- 실제 TLS 신뢰·DNS·LB는 외부 환경이므로 서버 검증 절차로 분리한다.

## 진행 기록
- 2026-09-16: 도메인과 경로 확정. 인증서는 사용자 사내 발급 후 등록한다.

- 2026-09-16: Headlamp 단위 테스트 7개, 고정 chart 렌더(baseURL·probe·TLS·권한), server-check, 서버 checkout 테스트 13개, README shell 구문 검사 통과. 실제 서버 접근·인증서 발급·TLS 접속은 미실행.
