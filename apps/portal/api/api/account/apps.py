"""Account 앱 설정입니다. 관리자 계정은 명시적인 관리 명령으로 생성합니다."""
from django.apps import AppConfig


class AccountConfig(AppConfig):
    """사용자·권한 모델을 등록하며 자동 권한 부여 시그널은 사용하지 않습니다."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.account"
