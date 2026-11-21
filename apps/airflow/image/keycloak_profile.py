"""Airflow SSO의 화면 표시값을 FAB 사용자 ID에 연결해 저장합니다."""

import logging
import re

from airflow import settings
from airflow.providers.fab.auth_manager.models import User
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger(__name__)
profiles = Table(
    'etch_keycloak_profile', MetaData(schema=User.__table__.schema),
    Column('user_id', ForeignKey(User.__table__.c.id, ondelete='CASCADE'), primary_key=True),
    Column('display_name', String(512), nullable=False),
)


def is_sso_username(username):
    return bool(re.fullmatch(r'kc_[0-9a-f]{64}', username or ''))


def save_display_name(session, user_id, display_name):
    """FAB 프로필 갱신과 같은 트랜잭션에서 최신 표시값을 저장합니다."""
    if not display_name:
        session.execute(delete(profiles).where(profiles.c.user_id == user_id))
        return
    insert = sqlite_insert if session.get_bind().dialect.name == 'sqlite' else pg_insert
    statement = insert(profiles).values(user_id=user_id, display_name=display_name)
    session.execute(statement.on_conflict_do_update(
        index_elements=[profiles.c.user_id], set_={'display_name': statement.excluded.display_name},
        where=profiles.c.display_name != statement.excluded.display_name,
    ))


def display_names(usernames):
    """화면에 나온 SSO 사용자만 한 번에 조회합니다. 일반 DB 사용자는 기존 이름을 표시합니다."""
    keys = {username for username in usernames if is_sso_username(username)}
    if not keys:
        return {}
    query = (
        select(User.username, User.first_name, User.last_name, profiles.c.display_name)
        .outerjoin(profiles, profiles.c.user_id == User.id)
        .where(User.username.in_(keys))
    )
    try:
        with settings.engine.connect() as connection:
            return {
                username: label or ' '.join(filter(None, (first, last))) or 'Keycloak 사용자'
                for username, first, last, label in connection.execute(query)
            }
    except SQLAlchemyError:
        log.warning('Airflow SSO 표시값을 조회할 수 없습니다.')
        return {}


if __name__ == '__main__':
    with settings.engine.begin() as connection:
        profiles.create(connection, checkfirst=True)
