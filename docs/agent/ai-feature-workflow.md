# Portal AI 개발 흐름

## 시작 위치와 읽기 범위

에디터·에이전트는 `apps/portal`에서 시작합니다. 단일 영역 작업은 `apps/portal/web` 또는
`apps/portal/api`에서 시작할 수 있습니다. 루트 지침과 [Portal 지침](../../apps/portal/AGENTS.md),
수정하는 영역의 하위 지침을 적용합니다. 다른 앱 작업은 해당 앱에서 별도 세션으로 시작합니다.

대상 feature → 관련 공통 코드·공개 facade → 필요한 외부 계약 순서로 확인합니다.
예를 들어 Portal에서 메일 화면을 수정할 때는 `rg '<검색어>' web/src/features/emails`부터 시작합니다.
의존이 확인되면 해당 facade나 공통 컴포넌트로 검색을 넓힙니다. 의존 방향은 Web·API 지침을 따릅니다.
전체 docs나 deploy를 미리 읽지 않으며, 인증·env·mock·파일 마운트 계약에 영향이 있을 때만 관련 지침을 읽습니다.

Codex는 시작 위치까지의 상위 AGENTS.md를 함께 읽습니다. 하위 폴더에서 시작해도 루트 지침이 없어지지는 않습니다.
따라서 루트는 공통 규칙, Portal은 개발 공통 규칙, Web·API는 각 경계를 소유합니다.
스킬도 작업에 맞는 본문만 읽습니다. 이 방식은 탐색 기본값이며 파일 접근을 차단하는 보안 경계는 아닙니다.

## 작업 프롬프트 예시

```text
Portal의 <feature>에서 <원하는 동작>을 구현해줘.
대상 feature부터 읽고 관련 공통 코드·공개 facade를 필요한 만큼 확인해줘.
인증·환경·배포 계약에 영향이 있으면 해당 영역 지침을 읽고 관련 설정까지 맞춰줘.
변경 영역에 맞는 검사를 실행하고 결과를 알려줘.
```

## 실행·검증

명령은 [Portal 시작 문서](../../apps/portal/README.md#개발검증)를 따릅니다.
Portal에서는 `make -C ../.. <target>`, Web·API에서는 `make -C ../../.. <target>`을 사용합니다.

- UI는 관련 테스트·린트·빌드와 UI audit, import/export/routing 변경은 Web boundary audit을 실행합니다.
- Django 업무 로직은 관련 테스트, 경계 변경은 API boundary audit, 모델 변경은 migration 검사를 실행합니다.
- Django 명령은 Compose api에서 실행하며 이미지 갱신·test env·migration 파일 보존은 테스트 스킬을 따릅니다.
- 환경·배포 설정은 변경된 앱의 검사만 선택합니다. 실행하지 못한 검증은 원인을 남깁니다.

`make dev`는 전체 로컬 Kubernetes 앱을 기동합니다. Portal 작업 범위와 실행 서비스 범위는 별개입니다.

## 탐색 범위 평가

[Portal 범위 평가](evals/portal-agent-scope.md)를 사용해 UI·API·인증 작업을 각각 새 세션에서 확인합니다.
변경 전후 같은 요청·시작 디렉터리·모델·도구 설정을 사용하고 다음을 기록합니다.

- 초기 적용 지침의 바이트 수(토큰 수를 직접 측정할 수 있으면 함께 기록).
- 읽은 고유 파일 수와 실제 읽기 횟수, 대상 feature 밖으로 확장한 이유.
- 무관한 앱 소스·운영 문서 읽기 여부와 필요한 외부 계약 누락 여부.
- 선택한 검사와 작업 결과의 정확성.

지침 분량 감소만으로 전체 토큰 절감률이나 작업 품질 개선을 주장하지 않습니다.
