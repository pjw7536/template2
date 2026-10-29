# 개발 안내

[문서 홈](../README.md) · [이전: 개념 이해하기](../concepts/README.md) · [다음: 참고 자료](../reference/README.md)

실행한 환경에서 수정할 코드를 찾고, 변경을 반영하고, 필요한 검사를 고르는 안내입니다.
이하 명령은 저장소 루트 기준입니다. 환경을 아직 준비하지 않았다면 [첫 셋업](../getting-started/01-setup.md)을 따릅니다.

## 수정하려는 영역 선택

| 작업 | 개발 설명 | 실행·검증 상세 |
| --- | --- | --- |
| 화면·상태·사용자 조작 | [Web 개발](01-frontend.md) | [Web 실행 안내](../../apps/portal/web/README.md) |
| API·업무 로직·DB 모델 | [API 개발](02-backend.md) | [API 실행 안내](../../apps/portal/api/README.md) |
| DAG·Airflow 이미지 | [Airflow 개발](../../apps/airflow/README.md) | 같은 문서의 개발·검증 절차 |
| 서버 DB 변경 적용 | [migration 적용](03-migration-guide.md) | [운영 overlay](../../deploy/portal/k8s/overlays/prod/README.md) |
| 설명·색인·문서 위치 | [문서 작성](04-documentation.md) | [문서 감사 도구](../../apps/tooling/README.md) |

## 기능 수정의 기본 흐름

1. [기능 안내](../modules/README.md)에서 목적·권한·데이터 흐름을 확인합니다.
2. 화면 변경은 `apps/portal/web/src/features/<feature>`, API 변경은 `apps/portal/api/api/<feature>`에서 시작합니다.
3. 해당 영역의 `AGENTS.md`와 [API 명세](../api/README.md)를 확인하고 필요한 코드만 수정합니다.
4. [변경 반영 명령](../getting-started/02-usage.md#소스-수정-반영)으로 실행할 이미지를 갱신합니다.
5. [영역별 검사](../getting-started/02-usage.md#변경-영역별-검사)를 실행하고 변경한 화면·API를 확인합니다.
6. 기능 설명·API 명세·구현 색인 중 변경의 영향을 받는 문서를 갱신합니다.

Web은 서버에서 받은 데이터를 React Query에 보관하고, UI 조작 상태는 컴포넌트나 Zustand에서 관리합니다.
API는 HTTP 처리·조회·쓰기 책임을 나눕니다. 다른 기능을 사용할 때는 공개 진입점(facade)을 통하며,
상세 기준은 Web·API 개발 설명에 있습니다.

외부 인증·메일·RAG 연결을 바꾼다면 소스뿐 아니라 로컬 mock과 설정 계약도 확인합니다.
앱의 배포 파일은 `deploy/<app>`, 개발 PC의 차이는 `local/<app>`이 소유합니다.
