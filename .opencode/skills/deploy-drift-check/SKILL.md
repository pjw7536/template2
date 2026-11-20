---
name: deploy-drift-check
description: 사내 관리 호스트의 현재 checkout 코드와 실제 Kubernetes 배포 상태가 같은지 조회 전용으로 대조하고 결과를 해석·보고한다. "서버가 레포와 같은지", "설정이 다 적용됐는지", "drift·불일치 점검", 정기 운영 점검 요청에 적용하며 배포 실행 자체에는 server-deploy-routine을 쓴다.
---

# deploy-drift-check

절차와 판정 해석의 원본은 [배포 상태 대조](../../../deploy/shared/docs/operations/04-drift.md)이고, 판정 규칙의 원본은 `deploy/shared/scripts/deploy_state.py`다. 이 스킬은 규칙을 다시 정의하지 않는다.

## 진행 방법
1. 조회만 한다. `*-up`, `kubectl apply|patch|delete|scale|rollout restart`는 이 스킬 범위가 아니다.
2. 최신 상태와 비교하려면 먼저 `git pull --ff-only`를 실행한다. 실패하면 현재 checkout으로 비교하고 그 사실을 보고한다.
3. 대상 앱·그룹 이름은 `deploy/shared/apps.json`에서 확인한다. 지정이 없으면 전체다.
4. [대조 실행](../../../deploy/shared/docs/operations/04-drift.md#대조-실행)의 명령을 `DRIFT_JSON=1`과 함께 실행한다. `KUBE_CONTEXT`는 항상 명시하고 값은 [운영 위치](../../../deploy/shared/docs/infrastructure/operations.md)의 서버 기본 context 또는 사용자가 지정한 값이다. 저장소 밖 env로 배포한 앱은 같은 `<APP>_ENV=<경로>`를 붙인다.
5. stdout의 JSON에서 `resultCode`와 `apps[].findings`를 읽고 [결과 해석과 조치](../../../deploy/shared/docs/operations/04-drift.md#결과-해석과-조치)로 해석한다. 유효한 JSON이 없으면 조회 실패로 보고한다. 출력에 없는 상태를 추정해 "정상"이라고 쓰지 않는다.
6. 조회 결과가 인프라 정보의 현재 값과 다르면 해당 원본을 `서버 조회` 상태로 갱신하고 `pending.md`를 정리한다. 그 외 파일은 수정하지 않는다.

## 보고 형식
- 기준 checkout: 브랜치·HEAD·미커밋 변경 여부
- 앱별 표: 앱 | 리소스 일치 수 | 판정(일치/DRIFT/WARN/UNKNOWN) | 다른 리소스·필드 요약 | 권장 조치
- 실행한 명령과 JSON 판정 및 근거, 조회하지 못한 항목, 수정한 문서 경로
- 재배포가 필요하면 대상 앱과 명령을 보고한다. 사용자가 배포까지 요청했다면 `server-deploy-routine`으로 이어서 진행한다.
- 결과를 외부 개발 환경에 전달해야 하면 `server-state-report`로 별칭 보고서를 만든다.
