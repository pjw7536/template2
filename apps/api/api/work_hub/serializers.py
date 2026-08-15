"""Work Hub HTTP 요청·응답 schema를 정의합니다."""

from rest_framework import serializers


class WorkHubGroupSerializer(serializers.Serializer):
    """Portal에서 선택할 수 있는 소속별 Grist 실행 정보입니다."""

    user_sdwt_prod = serializers.CharField()
    department = serializers.CharField()
    line = serializers.CharField()
    role = serializers.ChoiceField(choices=("viewer", "member", "manager"))
    launch_url = serializers.URLField()


class WorkHubContextSerializer(serializers.Serializer):
    """Work Hub launcher가 사용하는 현재 사용자 context입니다."""

    enabled = serializers.BooleanField()
    available = serializers.BooleanField()
    mode = serializers.ChoiceField(choices=("disabled", "single", "multiple", "unavailable"))
    reason = serializers.CharField(allow_blank=True)
    groups = WorkHubGroupSerializer(many=True)


class GristWebhookQuerySerializer(serializers.Serializer):
    """Grist Webhook URL에 포함할 document와 table 식별자를 검증합니다."""

    doc_id = serializers.CharField(max_length=128)
    table_id = serializers.CharField(max_length=64)


class GristWebhookPayloadSerializer(serializers.Serializer):
    """Grist가 전송하는 평탄한 record 배열을 검증합니다."""

    rows = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
        max_length=200,
    )

    def validate_rows(self, rows: list[dict]) -> list[dict]:
        """worker에 넘기기 전에 모든 WorkLog row ID를 검증합니다."""

        maximum_row_id = 9_223_372_036_854_775_807
        for index, item in enumerate(rows):
            row_id = item.get("id")
            if isinstance(row_id, bool):
                raise serializers.ValidationError(
                    f"{index}번째 item의 id가 올바르지 않습니다."
                )
            try:
                normalized_row_id = int(row_id)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    f"{index}번째 item의 id가 올바르지 않습니다."
                ) from exc
            if normalized_row_id < 1 or normalized_row_id > maximum_row_id:
                raise serializers.ValidationError(
                    f"{index}번째 item의 id가 올바르지 않습니다."
                )
        return rows
