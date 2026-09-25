# ExecPlan: Headlamp 최초 설치 안내 정리

## 목표
- README에서 시작해 준비 → TLS → Keycloak → API server → 배포·로그인 검증을 순서대로 완료한다.
- 실행 절차를 한 곳에 두고 참고·운영 문서를 분리한다.

## 현재 상태
- HTTPS·OIDC·서버 준비에서 context·검사·배포 명령이 반복된다.
- 필수 API server 상세 설정이 접힌 영역에 있고 최초 설치에 불필요한 원본 인증서까지 요구한다.
- env 이름과 문서의 고정 Secret 이름이 달라질 수 있다.
- server-check는 저장소 기본 env를, headlamp-check는 HEADLAMP_ENV를 검사한다.

## 범위
- deploy/headlamp 문서, 필요한 실행 도구·테스트 보완.
- 제거하는 문서의 외부 링크만 관련 문서에서 수정한다. 기존 Keycloak 작업은 보존한다.
- 실제 클러스터·Keycloak 권한은 변경하지 않는다.

## 설계
- 01 준비, env/02 변수 참고, 03 TLS, 04 Keycloak client·Secret, 05 API server, 06 배포·검증.
- operations/README.md에 장애·갱신·기존 조회 그룹 전환·복구를 모은다.
- OIDC.md와 HTTPS_CERTIFICATE_GUIDE.md는 내용 이관 후 삭제하고 들어오는 링크를 갱신한다.
- env의 검증된 공개 설정을 읽는 setup-env 출력을 제공해 이후 명령에 일관되게 전달한다.
- 공용 인증서 문서는 PFX/P7B 추출 참고로 사용하며 Headlamp 배포 명령 중복을 제거한다.

## 실행 단계
- [x] 문서·도구·현재 Keycloak 계약 대조
- [x] 준비 입력 및 순서별 문서 작성
- [x] 중복 문서 제거와 외부 링크 정리
- [x] 문서 명령·링크·배포 검사 및 테스트 검증

## 검증
- 변경 문서의 로컬 링크와 Bash 블록 문법 검사.
- Python Headlamp 테스트와 Node Headlamp 배포·서버 checkout 테스트.
- make server-check APP=headlamp PROFILE=prod, make headlamp-check.
- git diff --check. 실제 브라우저·사내망 검증은 실행 환경 부재를 명시.

## 위험과 대응
- API server 설치 방식은 명시되지 않았다. kubeadm static Pod 예와 기존 인증 방식별 분기를 제시하고 모든 제어면 담당자의 반영을 완료 조건으로 둔다.
- 외부 env와 기본값 불일치: 검증한 공개 설정을 안내 명령에 재사용한다.
- 기존 링크 단절: 참조 검색과 상대경로·앵커 검사로 확인한다.

## 진행 기록
- 2026-09-25: 중복 절차와 누락된 최초 설치 전제 확인. 기존 기능 변경보다 실행 흐름 정리를 중심으로 진행한다.
- 2026-09-25: 01·03~06 실행 문서와 운영 참고로 이관, OIDC/HTTPS 중복 문서 삭제 및 외부 참조 갱신. 과거 작업 기록에 나온 삭제 전 파일명은 역사적 기록으로 유지.
- setup-env가 검증한 공개 입력·callback·SSO host를 출력해 사용자 지정 이름도 안내 명령에 전달한다. client import JSON도 수동 설정과 동일하게 RS256을 명시한다.
- 문서 8개, Bash 블록 28개 구문, 로컬 링크·앵커 59개 통과. 임시 DER 루트·PEM 중간 CA·서버 인증서로 03의 검증 블록 실제 실행 통과. 사용자 지정 env로 01의 변수 읽기 블록 실행 통과.
- Python 15개·Node 배포/서버 checkout 19개 테스트, server-check/headlamp-check, git diff --check 통과. Helm은 기존 `/tmp/tailwind-commit-tools/linux-amd64/helm`을 HELM_BIN으로 지정.
- 운영 context·사내망·실제 인증서가 없는 환경이므로 실제 클러스터 적용·브라우저 로그인은 미실행. 05의 모든 제어면 반영과 06의 실제 로그인·권한·갱신을 완료 기준으로 명시.
