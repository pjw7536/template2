---
name: deploy-drift-check
description: 사내 CP1의 현재 checkout 코드와 실제 Kubernetes 배포 상태가 같은지 조회 전용으로 대조하고 결과를 해석·보고한다. "서버가 레포와 같은지", "설정이 다 적용됐는지", "drift·불일치 점검", 정기 운영 점검 요청에 적용하며 배포 실행 자체에는 server-deploy-routine을 쓴다.
---

# deploy-drift-check

## 목적
현재 checkout의 배포 정의와 실제 서버 상태의 차이를 결정적 스크립트로 판정하고, 사람이 바로 조치할 수 있게 근거와 다음 단계를 보고한다.
판정 규칙의 원본은 `deploy/shared/scripts/deploy_state.py`와 [배포 상태 대조](../../../deploy/shared/docs/operations/04-drift.md)다. 이 스킬은 판정 규칙을 다시 정의하지 않는다.

## 원칙
- 조회만 한다. `*-up`, `kubectl apply|patch|delete|scale|rollout restart`, `git pull|fetch|reset|checkout`, Secret 조회는 이 스킬 범위가 아니다. 비교 기준은 현재 checkout이며 원격 최신화는 사용자가 한다.
- `KUBE_CONTEXT`는 항상 명시한다. 값은 [운영 위치](../../../deploy/shared/docs/infrastructure/operations.md)의 서버 기본 context 또는 사용자가 지정한 값이다.
- 스크립트 결과를 그대로 근거로 쓰고, 출력에 없는 상태를 추정해 "정상"이라고 쓰지 않는다.

## 절차
1. 대상 확인: 앱·그룹 이름은 `deploy/shared/apps.json`에서 확인한다. 지정이 없으면 `all`.
2. 실행(CP1 저장소 루트):
   - `make drift-check APP=<app|group> KUBE_CONTEXT=<context> DRIFT_JSON=1`
   - 저장소 밖 env로 배포하는 앱은 배포 때와 같은 `<APP>_ENV=<경로>`를 함께 지정한다. 경로는 사용자 또는 인프라 운영 위치 문서에서 확인한다.
   - Helm·chart 미준비 등으로 렌더가 안 되면 `UNKNOWN manifest`로 남기고, 원인을 보고한 뒤 필요하면 `DRIFT_SKIP_MANIFEST=1`로 나머지만 확인한다.
3. 종료 코드 해석: `0` 일치, `1` DRIFT/WARN 있음, `2` 판정 불가(기록 없음·조회 실패·입력 오류).
4. `manifest` 판정을 우선한다. 항목별 해석·조치는 04-drift.md의 결과 해석 표를 따른다. 필요하면 다음 조회로 근거를 보강한다.
   - `kubectl --context <ctx> -n <ns> rollout history <kind>/<name>`
   - `kubectl --context <ctx> -n <ns> get events --sort-by=.lastTimestamp | tail -30`
   - `git log --oneline <배포 commit>..HEAD -- <앱 경로>`
5. 인프라 정보 반영: 조회 결과가 `deploy/shared/docs/infrastructure/`의 현재 값과 다르면 해당 원본을 `서버 조회` 상태로 갱신하고, 서버 작업이 남으면 `pending.md`에 행을 추가한다. 적용이 확인된 pending 행은 삭제한다. 그 외 파일은 수정하지 않는다.

## 보고 형식
- 기준 checkout: 브랜치·HEAD·미커밋 변경 여부
- 앱별 표: 앱 | 리소스 일치 수 | 판정(일치/DRIFT/WARN/UNKNOWN) | 다른 리소스·필드 요약 | 권장 조치
- 실행한 명령과 종료 코드, 조회하지 못한 항목, 수정한 문서 경로
- 재배포가 필요하면 대상 앱과 명령을 제안만 하고 실행은 사용자 승인 후 `server-deploy-routine`으로 진행한다.
