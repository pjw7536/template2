# Eval: Offsite Contract Sync

## Task
auth, RAG, assistant, mail 중 하나의 external contract 또는 local dummy 연동을 변경한다.

## Success Criteria
- intranet URL을 hardcode하지 않는다.
- env var 기반 설정을 유지한다.
- `local/AGENTS.md`를 적용하고 api-k8s.env 및 생성된 runtime env의 합성 순서를 유지한다. 생성 파일을 직접 수정하지 않는다.
- `local/portal/k8s`, `local/shared/scripts/k8s_config.py`, `local/portal/env/api.env`, `local/adfs_dummy` 영향 여부를 확인한다.
- corporate network 없이 local dummy flow가 깨지지 않는지 점검한다.
- 변경된 request/response shape를 관련 docs 또는 tests에 반영한다.

## Regression Notes
- mock 반영이 필요 없다고 판단하면 이유를 명시한다.
