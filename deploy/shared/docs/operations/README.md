# 공통 앱 배포와 운영

[전체 배포 안내](../../../README.md) · [최초 설치의 의존 관계](applications.md) · [CP1 파일 관리](files.md)

서버는 준비된 이미지·배포 정의·실제 env로 필요한 앱만 검사하고 기동합니다.
명령은 관리 호스트의 저장소 루트에서 실행하며, 각 앱의 절차에 지정된 실제 context와 env를 사용합니다.

## 작업별 시작점

| 하려는 일 | 문서 |
| --- | --- |
| 서버에 필요한 파일 받기·앱 범위 변경 | [선택 checkout](checkout.md) |
| Git 갱신·운영 입력·파일 보관 관리 | [관리 호스트 파일 관리](files.md) |
| 이미지·chart·DB·디스크·env·권한 준비 | [앱 배포 준비](prepare.md) |
| 의존 서비스와 설치 순서 확인 | [앱별 배포 순서](applications.md) |
| 실제 HTTPS·로그인·업무 기능 확인 | [접속·기능 검증](verify.md) |
| 설정·이미지 갱신·장애 조회·백업 | [갱신과 문제 해결](maintenance.md) |

## 준비 순서

| 순서 | 할 일 | 원본 문서 |
| --- | --- | --- |
| 1 | 관리할 앱의 파일과 실제 대상 확인 | [선택 checkout](checkout.md)·[현재 환경 조회](../kubernetes/baseline.md) |
| 2 | 이미지·chart·DB·디스크·env·인증서 준비 | 해당 앱 README의 준비·설정 문서 |
| 3 | 의존 서비스와 실제 입력 확인 | [최초 설치 순서](applications.md)·[환경설정 검사](../configuration/environment.md#설정-검사) |
| 4 | 저장소 원본 검사 후 실제 대상 검사 | 해당 앱의 배포 절차. 정적 검사와 서버 상태 검사를 구분 |
| 5 | 검사한 env·context로 적용 | 해당 앱의 배포 절차와 완료 기준 |
| 6 | rollout·접속·로그인·업무 동작 확인 | [접속·기능 검증](verify.md) |

서버 검사·렌더·배포는 앱 소스와 local 파일 없이 진행합니다. 이미지를 직접 빌드하는 경우에만 앱 소스를 추가합니다.
Airflow DAG가 Portal 업무 API를 호출한다면 해당 Portal API도 준비돼 있어야 합니다.

## 앱별 실행 안내

| 앱 | 설치·검사·기동 | 설치 후 운영 |
| --- | --- | --- |
| Keycloak | [설치 순서](../../../keycloak/README.md) | [파일·설정 반영](../../../keycloak/docs/08-operations.md) |
| Airflow | [설치 순서](../../../airflow/README.md) | [백업·이전·업데이트](../../../airflow/docs/06-operations.md) |
| MinIO | [설치 순서](../../../minio/README.md) | [버킷·이전·재생성](../../../minio/docs/03-operations.md) |
| Monitoring | [설치 순서](../../../monitoring/README.md) | [갱신·백업·장애](../../../monitoring/docs/04-operations.md) |
| Headlamp | [설치 순서](../../../headlamp/README.md) | [Secret·CA·권한·복구](../../../headlamp/docs/07-operations.md) |
| FTP | [설치 순서](../../../ftp/README.md) | [접속·노드·계정](../../../ftp/docs/03-operations.md) |
| Portal | [설치 순서](../../../portal/README.md) | [설정 반영·health](../../../portal/docs/05-operations.md) |

## 설정 변경 후 반영

Git 갱신만으로 실행 중인 앱이 바뀌지는 않습니다.
이미지 변경은 해당 앱의 새 태그·배포, env 변경은 검사·Secret 등록·필요한 Pod 재시작,
인증서 변경은 공용 TLS 또는 CA 갱신 절차를 따릅니다. DB schema 변경은 해당 migration 절차를 수행합니다.
외부 DB·OIDC·MinIO 계정은 실제 서비스 계정과 앱 설정을 함께 맞춥니다.
실패하면 해당 단계의 로그와 완료 기준을 확인하고, 원인 해결 후 같은 입력으로 재검사합니다.
