# ExecPlan: Keycloak 배포 파일 전체 점검

## 목표
- deploy/keycloak의 문서·입력·스크립트·manifest·렌더 정합성을 확인한다.
- examples를 실제 용도의 입력 폴더로 바꾸고 불필요한 실행 코드를 정리한다.

## 현재 상태
- 최초 설치 문서 정리는 작업트리에 있으며 보존한다.
- examples에 빈 입력 템플릿과 가상 CSV가 섞여 있다.
- claim Job에 수정 완료된 realm 옵션의 실행 시 치환이 남아 있다.
- SDWT 등록은 client 미지정에도 scope 검사를 실행한다.

## 범위
- Keycloak 원본·문서, 직접 참조 테스트·입력 fixture, 필요 시 참조 링크.
- 실제 credential·클러스터·사용자 데이터는 변경하지 않는다.

## 설계
- inputs는 운영자가 복사해 작성하는 빈 CSV 템플릿만 소유한다.
- 가상 CSV는 apps/tooling/tests/fixtures/keycloak-sdwt로 옮긴다.
- claim Job은 최신 ConfigMap 스크립트를 직접 실행하고 사용하지 않는 Portal env를 제거한다.
- SDWT client 미지정 시 client/scope API에 접근하지 않는다.
- 통합 실행·렌더·속성 이관은 기존 Make/운영 문서에서 참조하므로 무조건 삭제하지 않는다.

## 실행 단계
- [x] 전체 파일과 참조를 대조한다.
- [x] 확인된 불일치·불필요 코드·입력 경로를 수정한다.
- [x] 렌더·관련 회귀 검사·문서 검증을 실행한다.

## 검증
- Python Keycloak 및 server-up 테스트, Node environment/server-checkout/k8s-routing.
- Bash/Python/JSON 구문, 문서 링크·앵커, Make 진입점, 입력 CSV 검사.
- make k8s-export APP=keycloak PROFILE=prod 및 server-check, 렌더 재생성 일치.

## 위험과 대응
- 사용하는 호환 진입점 삭제: 호출자 확인 후 유지하고 원본 참고에 용도를 기록한다.
- 입력 데이터 혼동: 운영 입력 템플릿과 가상 테스트 CSV를 물리적으로 분리한다.
- 실제 동작 보장 범위: 정적·mock 검사와 실제 서버 로그인 검증을 구분한다.

## 진행 기록
- 2026-09-25: 파일 전수 목록과 Make·공통 도구·테스트·운영 문서 참조를 확인했다.

## 점검 결과

| 영역 | 확인·조치 |
| --- | --- |
| 최초 설치 문서 | 서버 → 자체 설정·SDWT → Account Console → 앱 연결 순서, 입력 키·단계명·링크 확인 |
| 입력 데이터 | inputs에 헤더 전용 템플릿 2개. 가상 CSV 2개는 tooling fixture로 이동하고 읽기 경로 갱신 |
| env | credential 값은 유지. 통합 명령을 안내하던 주석만 단계별 문서로 수정 |
| 서버 원본 | 이미지 버전·worker·PV/PVC·probe·Secret·realm import·공용 ingress 참조와 문서 대조 |
| IdP·mapper Job | 수정 완료된 realm 옵션의 임시 cp/sed 치환과 IdP Job의 미사용 Portal client env 제거 |
| mapper 원본 | 사내 claim 저장명과 기본 필드 예외 확인. account_user 기준이라는 낡은 주석·로그 수정 |
| SDWT | client 없는 등록에서 client/scope 검사 생략. 실제 사용자·그룹 생성 보존 및 신원 충돌 검사 유지 |
| 이관 도구 | 참조하는 Make 진입점·테스트가 있어 유지. 오래된 단계 번호를 제거 |
| Discovery·단계 실행 | env 사전 검사·명시 context·단계별 Job·Secret 의존성 확인. 공통 env resolve 호출이 있어 유지 |
| 렌더·export | 실제 CP1 문서·Make·검사에서 참조하므로 유지. 기본 스택과 전달 스택의 감시 범위를 혼동하던 테스트 수정 |
| 셸 진입점 | 모두 Make 명령이 참조하므로 유지. 중복 설정 구현이 아닌 단일 실행 진입점 |

## 검증 결과

- Python Keycloak 39개(실서버 9개는 별도 실행), Keycloak 서버 도구 13개, Node environment/server-checkout/k8s-routing 61개 확인.
- 로컬 공식 Keycloak 26.7.1 이미지로 임시 loopback 서버를 실행해 SDWT 17개(실제 통합 9개 포함) 통과, 컨테이너 제거. 전체 고유 테스트 113개 통과.
- Keycloak 내 Python 4개·Bash 11개·JSON 3개 구문 확인.
- 문서 링크·앵커 75개, Bash 예제 블록 22개, Make 진입점 9개 확인.
- server-check 통과. 렌더 YAML 2개를 원본에서 생성하고 반복 생성의 바이트 일치 확인.
- examples 경로와 임시 realm 치환 코드 잔여 참조 없음. git diff --check 통과.
- 운영 서버·사내 Discovery·실제 broker 로그인·외부 앱 연결에는 접근하지 않았다. 이 부분의 성공은 로컬 검증만으로 보장하지 않는다.
