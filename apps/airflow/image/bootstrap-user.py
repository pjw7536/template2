"""Helm 초기화 Job에서 Secret으로 받은 관리자를 생성하고 기존 계정은 유지한다."""

import os
import subprocess

from airflow.www.app import cached_app


def main():
    """동일 사용자 재생성을 피하고 생성 실패는 Job 실패로 전달한다."""
    # 기존 airflow-init와 같이 기본 pool의 slots를 무제한으로 맞춘다.
    subprocess.run(["airflow", "pools", "set", "default_pool", "-1", "기본 task pool 제한 없음"], check=True)
    app = cached_app()
    with app.app_context():
        manager = app.appbuilder.sm
        username = os.environ["AIRFLOW_ADMIN_USERNAME"]
        if manager.find_user(username=username):
            print("기존 관리자 계정을 유지합니다.")
            return
        user = manager.add_user(
            username=username,
            first_name="Airflow",
            last_name="Admin",
            email=os.environ["AIRFLOW_ADMIN_EMAIL"],
            role=manager.find_role("Admin"),
            password=os.environ["AIRFLOW_ADMIN_PASSWORD"],
        )
        if not user:
            raise RuntimeError("Airflow 관리자 생성 실패")
        print("관리자 계정을 생성했습니다.")


if __name__ == "__main__":
    main()
