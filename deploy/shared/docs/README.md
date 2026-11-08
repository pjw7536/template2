# 공통 배포 문서 안내

[배포 문서 홈](../../README.md) · [사내 인프라 정보](infrastructure/README.md)

여러 앱이 공유하는 서버 환경·Kubernetes 설치·운영·명령어 참고의 색인입니다.
공통 절차는 이 폴더에 모으며 모든 서버 선택 checkout에 포함됩니다.
`deploy/shared/ingress`와 `deploy/shared/certs`는 실행 원본·인증서 파일의 위치입니다.
앱별 배포 명령과 입력은 [앱별 시작점](../../README.md#앱별-배포와-상세-작업)에서 해당 앱 안내로 이동합니다.
앱 README에서 설치 순서를 고르고, `docs/`의 준비·환경설정·배포·운영 문서에서 실제 절차를 읽습니다.

## 하려는 일에 맞게 찾기

| 하려는 일 | 시작 문서 | 상세 원본 |
| --- | --- | --- |
| 사내 운영 정보 확인·변경 기록 | [사내 인프라 정보](infrastructure/README.md) | 주제별 원본·기록 양식·에이전트 갱신 절차 |
| 서버·OS·버전 확인 | [서버·노드](infrastructure/servers.md) | 노드명·IP·역할·설치 기준 |
| VIP·DNS·연결 경로 확인 | [네트워크](infrastructure/network.md) | backend·네트워크 구성·남은 확인 |
| 서비스 URL·앱 배치·스토리지 확인 | [서비스](infrastructure/services.md) | 접속 주소·namespace·배치·업무 연동 |
| 이미지·패키지 미러 확인 | [저장소·미러](infrastructure/repositories.md) | 실제 주소·전체 public/mirror 이름 매핑 |
| 운영 파일·백업·담당자 확인 | [운영 위치·책임](infrastructure/operations.md) | 파일·데이터 보관 위치·운영 책임 |
| 기존 서버의 실제 상태 조회 | [현재 환경 확인](kubernetes/baseline.md) | 확인값은 주제별 원본에 반영 |
| 새 클러스터 구성·Worker 추가 | [Kubernetes 셋업](kubernetes/README.md) | 제어면·Worker·클러스터 인수·상태 조회 |
| 공용 HTTPS·APP VIP·라우팅·확장 | [공용 Ingress](ingress/README.md) | 최초 설치·운영 기준·기존 배치 확장·복구 |
| env·Secret 입력 준비 | [앱별 환경설정](configuration/environment.md) | 설정 소유권·입력 파일·검사·등록 |
| 인증서·CA 추출·갱신 | [인증서 관리](certificates/README.md) | 사이트별 인증서·공용 CA와 TLS 등록 |
| 서버 파일 준비·앱 선택 | [선택 checkout](operations/checkout.md) | [CP1 Git·배포 파일 관리](operations/files.md) |
| 앱 설치·갱신·기동 | [서버 기동](operations/README.md) | [앱 배포 순서](operations/applications.md) |
| 배포 후 접속·로그인 확인 | [완료 확인](operations/verify.md) | 실제 HTTPS·로그인·업무 동작 검증 |
| 장애·업데이트·백업 대응 | [운영 안내](operations/maintenance.md) | 앱별 상세 절차와 복구 확인 |
| kubectl 명령어 찾기 | [명령어 참고](kubernetes/kubectl.md) | 상태·로그·권한 조회, 변경·삭제 명령의 구분 |

## 정보별 관리 위치

| 정보 종류 | 원본 | 작성 기준 |
| --- | --- | --- |
| 사내 운영 정보 | `infrastructure/`의 주제별 원본 | README의 분류·기록 양식과 하위 AGENTS.md에 따라 현재 값·확인 근거·남은 확인을 유지 |
| 실행 설정 | 해당 앱의 manifest·env·Helm values | 실제 입력은 소유 앱에서 변경하고 문서의 현황과 대조 |
| 클러스터 절차 | `kubernetes/` | 제어면·Worker 설치, 공통 준비·용어·상태 조회 |
| 공용 진입점 | `ingress/` | Traefik·VIP·라우팅·배치 확장 |
| 인증서 | `certificates/` | 파일 준비·추출·검증·공용 TLS 적용·갱신 |
| 앱 배포와 운영 | `operations/` | checkout·파일 관리·앱 의존 관계·검증·유지보수 |
| 공통 설정 계약 | `configuration/` | env·Secret 입력·검사·등록 |

이 색인에는 운영 주소·전체 설정 표를 반복하지 않고 상세 원본을 연결합니다.
설치 절차에서 필요한 버전·주소·명령은 해당 절차에 유지하되 환경이 바뀌면 현황·실행 입력과 함께 대조합니다.
서버 작업에 필요한 설명은 `deploy` 안에서 읽을 수 있게 하고, 루트 `docs`에서는 그 원본으로 연결합니다.
