---
name: server-deploy-routine
description: 사내 CP1에서 저장소의 확정 커밋을 Kubernetes에 배포·갱신하는 운영 절차. 앱 설치·업데이트·재배포·env/Secret 갱신 요청에 적용한다. 코드·manifest 수정은 하지 않으며 상태 점검만 필요하면 deploy-drift-check를 쓴다.
---

# server-deploy-routine

## 목적
사내 운영 agent가 저장소를 고치지 않고, 앱 문서의 원본 절차대로 검사 → 적용 → 기록 → 확인을 수행하게 한다.

## 원칙
- 저장소 코드·manifest·env 원본·스크립트를 수정하지 않는다. 배포가 막히는 원인이 저장소에 있으면 원인과 필요한 수정만 보고하고 중단한다. 문서 수정은 `deploy/shared/docs/infrastructure/`의 운영값 갱신만 한다.
- 명령은 각 앱 README·docs가 원본이다. 이 스킬에 적힌 예시보다 앱 문서를 우선한다.
- 클러스터를 바꾸는 명령(`make *-up`, `*-setup`, `*_APPLY=1`, `kubectl apply|patch|delete|scale|rollout restart`, `helm upgrade`)은 실행 전 대상·context·명령·영향을 보여 주고 사용자 승인을 받는다. 조회·검사 명령은 승인 없이 실행한다.
- `KUBE_CONTEXT`를 항상 명시하고, Secret 값·env 내용·토큰을 출력하거나 문서에 쓰지 않는다.
- DB·PV·PVC·데이터 폴더를 삭제·이동하지 않는다. 앱 문서가 요구하는 백업 단계를 건너뛰지 않는다.

## 절차
1. 전제 확인
   - `deploy/shared/docs/infrastructure/README.md`와 `pending.md`에서 대상 앱 관련 행을 읽는다.
   - 대상 앱의 `deploy/<app>/README.md`와 그 README가 지정한 설치·운영 문서를 읽는다.
2. checkout 확인: checkout 최신화는 사용자가 한다. agent는 `git pull`·`fetch`·`checkout`을 실행하지 않는다.
   - `git status --short`, `git branch --show-current`, `git log -1 --oneline`으로 배포할 commit을 보고한다.
   - 앱 경로에 미커밋 변경이 있으면 멈추고 보고한다.
3. 배포 전 대조: `make drift-check APP=<app> KUBE_CONTEXT=<ctx>`로 현재 서버 상태와 변경 파일을 확인한다. 예상하지 못한 DRIFT(수동 수정 등)가 있으면 덮어쓰기 전에 보고한다.
4. 검사: `make server-check APP=<app> PROFILE=prod`와 앱 문서의 `*-check`·env 검사를 실행한다. 실패하면 적용하지 않는다.
5. 적용(승인 후): 앱 문서의 배포 명령을 실행한다.
   - `make <app>-up`은 성공 시 배포 기록을 자동으로 남긴다.
   - 직접 명령(`kubectl apply -k`, `manage.py deploy` 등)으로 배포했으면 rollout 완료 후 `make deploy-record APP=<app> KUBE_CONTEXT=<ctx> RECORD_INPUTS="<저장소 밖 입력 파일>"`을 실행한다.
6. 사후 확인: 앱 문서의 완료 기준, `make drift-check APP=<app> KUBE_CONTEXT=<ctx>`가 `0`인지, 필요한 접속 검증을 확인한다.
7. 운영 정보 반영: 적용·확인된 값은 인프라 원본을 `서버 조회` 상태로 갱신하고 완료된 `pending.md` 행을 삭제한다. 남은 작업은 행으로 추가한다.

## 실패 시
- 실패 단계·명령·종료 코드·오류 요약(비밀값 제외)과 관련 `kubectl describe|logs|get events` 조회 결과를 보고한다.
- 롤백이 필요하면 앱 문서의 복구 절차를 제시하고 승인 후 수행한다. 문서에 절차가 없으면 임의로 만들지 않는다.

## 보고 형식
- 대상 앱·context·배포 commit(전/후)
- 실행한 명령과 결과(검사/적용/기록/확인 구분)
- drift-check 최종 결과, 갱신한 문서 경로, 남은 서버 작업
