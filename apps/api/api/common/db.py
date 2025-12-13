"""API에서 사용할 데이터베이스 헬퍼 함수 모음."""
from __future__ import annotations

from contextlib import contextmanager  # with 문에서 자원 자동 정리용
from typing import List, Optional, Sequence

from django.db import connection  # Django의 DB 연결 객체 (커서 획득용)


def _dictfetchall(cursor) -> List[dict]:
    """
    ✅ 커서(cursor)에서 모든 결과 행을 딕셔너리 리스트 형태로 반환.

    - 일반적으로 cursor.fetchall()은 튜플 리스트를 반환하지만,
      이 함수는 각 행을 {"컬럼명": 값, ...} 형태의 dict로 바꿔줍니다.
    - ORM이 아닌 raw SQL 실행 시, JSON 응답 변환 등에 자주 사용됩니다.
    """
    # cursor.description 은 SELECT 결과의 컬럼 정보 목록
    columns = [col[0] for col in cursor.description] if cursor.description else []
    # zip(columns, row)로 컬럼명-값 쌍을 묶어 dict 생성
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@contextmanager
def get_cursor():
    """
    ✅ 데이터베이스 커서를 안전하게 열고 닫아주는 컨텍스트 매니저.

    - with get_cursor() as cursor: 형태로 사용하면
      블록 종료 시 자동으로 커서가 close 됩니다.
    - Django의 connection.cursor()를 thin wrapper 형태로 감쌌습니다.
    """
    with connection.cursor() as cursor:  # pragma: no cover: 단순 래퍼라 테스트 제외
        yield cursor


def run_query(sql: str, params: Optional[Sequence[object]] = None) -> List[dict]:
    """
    ✅ SELECT 계열 쿼리를 실행하고 결과를 딕셔너리 리스트로 반환.

    예:
        rows = run_query("SELECT id, name FROM users WHERE active=%s", [True])

    반환 예시:
        [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return _dictfetchall(cursor)


def execute(sql: str, params: Optional[Sequence[object]] = None) -> tuple[int, Optional[int]]:
    """
    ✅ INSERT / UPDATE / DELETE 같은 데이터 변경 쿼리 실행.

    반환값:
        (rowcount, lastrowid)
        - rowcount: 영향받은 행(row)의 수
        - lastrowid: 마지막으로 생성된 PK (DB 백엔드에 따라 없을 수도 있음)

    예:
        count, new_id = execute(
            "INSERT INTO items (name) VALUES (%s) RETURNING id", ["item1"]
        )
    """
    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        lastrowid = None

        # 결과가 있는 경우 (예: RETURNING id)
        if cursor.description:
            try:
                row = cursor.fetchone()
            except Exception:  # 방어 코드: 결과가 비정상일 경우
                row = None
            if row:
                lastrowid = row[0]
        else:
            # SQLite/MySQL의 lastrowid 속성 사용
            lastrowid = getattr(cursor, "lastrowid", None)

        # 영향받은 행 개수와 마지막 ID 반환
        return cursor.rowcount, lastrowid

