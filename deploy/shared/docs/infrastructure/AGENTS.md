# 사내 인프라 정보 관리 지침

분류·기록 규칙·확인 상태·입력 양식은 [README](README.md)가 원본이다. 상위 공통 규칙을 반복하지 않고 이 영역의 갱신·검증만 정한다.

## 갱신

- 작업 주제의 원본만 추가로 읽고 현재 값·확인 상태·설정 원본·남은 확인을 전제로 사용한다. 실제 적용 전 필요한 최신 상태를 조회하거나 사용자에게 확인한다.
- 새 운영값은 README 규칙에 따라 원본에 반영한다. 정보 기록을 서버 적용으로 확대하지 않는다.
- 저장소 선언 변경으로 재적용이 필요하면 [pending](pending.md)에 추가하고 서버 적용이 확인되면 해당 행을 제거한다.
- 실행 입력 수정은 소유 앱의 manifest·env·Helm values·설치 절차와 README 분류표의 대조 대상을 함께 확인한다.
- 서버·VIP·사내 host의 이름·주소를 추가·변경하면 `aliases.json`을 함께 고친다. 별칭은 제어면 `N-CP<n>`, Worker `N-W<n>`, 관리 전용 `N-M<n>`, 그 밖은 용도 이름을 쓰고 기존 별칭의 의미를 바꾸지 않는다.
- 사내망 밖으로 전달할 내용에는 실제 서버명·IP·사내 도메인을 쓰지 않고 별칭만 쓴다.
- 클러스터 밖 작업의 접근 방법은 [접근 경로](access.md) 한 곳에만 적는다. 다른 문서는 그 절을 링크한다. 절 제목을 바꾸면 `deploy/shared/scripts/ops_preflight.py`의 `볼 곳` 앵커와 문서의 링크를 함께 고친다. 비밀값은 쓰지 않고 위치만 적는다.

## 검증

- 문서만 변경하면 링크·앵커·`git diff --check`와 `make audit-docs`를 확인한다.
- 주소·별칭을 바꾸면 `python3 -m unittest discover -s deploy/shared/tests -p 'test_ops_tools.py'`로 별칭 표와 문서의 일치를 확인한다.
- 문서 이동·공통 경로 변경은 `node --test apps/tooling/tests/server-checkout.test.cjs`를 추가하고 기존 주소·서버/IP·VIP backend 대응·전체 미러 목록의 보존을 대조한다.
- 갱신 내용·검증 결과·실제 서버 조회 여부·남은 확인을 구분해 보고한다.
