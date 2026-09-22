from . import *  # noqa: F403


class ObserverAnalysisPart2Tests(TestCase):
    """Observer 분석 context와 runtime 계약을 검증합니다."""

    def setUp(self) -> None:
        """보호된 분석 endpoint를 호출할 인증 사용자를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S-OBSERVER-AI",
            password="test-password",
            knox_id="knox-observer-ai",
        )
        self.client.force_login(self.user)
        self.start_at = datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Seoul"))
        self.end_at = datetime(2026, 8, 3, 23, 59, 59, tzinfo=ZoneInfo("Asia/Seoul"))

    def test_analysis_context_honors_selected_tip_group(self) -> None:
        """선택하지 않은 TIP group의 L*_TIP 상태는 분석에서 제외합니다."""

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["tip"],
            selected_tip_groups=["LINE-A_PROC-A_1200_PPID-1"],
            logs_by_type={
                "tip": [
                    {
                        "id": "TIP-1",
                        "logType": "TIP",
                        "eventType": "L1_TIP",
                        "eventTime": "2026-08-02T09:50:00+09:00",
                        "lineId": "LINE-A",
                        "process": "PROC-A",
                        "step": "1200",
                        "ppid": "PPID-1",
                    },
                    {
                        "id": "TIP-2",
                        "logType": "TIP",
                        "eventType": "L2_TIP",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                        "lineId": "LINE-A",
                        "process": "PROC-B",
                        "step": "2200",
                        "ppid": "PPID-2",
                    },
                ]
            },
        )

        self.assertEqual(len(context["tipStatusStatistics"]), 1)
        self.assertEqual(context["tipStatusStatistics"][0]["process"], "PROC-A")

    def test_analysis_context_keeps_ctttm_chronological_summary_as_background(self) -> None:
        """CTTTM 핵심요약과 시간순 이벤트 정리를 별도 context column에 보존합니다."""

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["eqp", "ctttm"],
            selected_tip_groups=["__ALL__"],
            logs_by_type={
                "eqp": [
                    {
                        "id": "EQP-DOWN",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                    }
                ],
                "ctttm": [
                    {
                        "id": "WO-1",
                        "logType": "CTTTM",
                        "eventType": "CBM",
                        "eventTime": "2026-08-02T09:50:00+09:00",
                        "comment": "정기 점검",
                        "coreSummary": "압력 계통 점검",
                        "summary": "09:30 알람 확인 → 09:40 부품 교체 → 09:45 정상화",
                    }
                ],
            },
        )

        columns = context["contextEvents"]["columns"]
        row = context["contextEvents"]["rows"][0]
        self.assertEqual(row[columns.index("summary")], "압력 계통 점검")
        self.assertEqual(
            row[columns.index("chronologicalSummary")],
            "09:30 알람 확인 → 09:40 부품 교체 → 09:45 정상화",
        )
        self.assertEqual(context["schemaVersion"], "observer-analysis-v1")

    def test_analysis_context_applies_esop_ctttm_racb_llm_contract(self) -> None:
        """ESOP·CTTTM·RACB 주변 로그를 LLM 전용 계약으로 축약합니다."""

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["eqp", "esop", "ctttm", "racb"],
            selected_tip_groups=["__ALL__"],
            logs_by_type={
                "eqp": [
                    {
                        "id": "EQP-DOWN",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                    }
                ],
                "esop": [
                    {
                        "id": "ESOP-1",
                        "logType": "ESOP",
                        "eventType": "SAMPLE",
                        "eventTime": "2026-08-02T09:40:00+09:00",
                        "status": "OPEN",
                        "comment": "sample wafer 검증 정상 $@$ 내부 상세 정보",
                    }
                ],
                "ctttm": [
                    {
                        "id": "WO-1",
                        "logType": "CTTTM",
                        "eventType": "CBM",
                        "eventTime": "2026-08-02T09:45:00+09:00",
                        "comment": "정기 PM",
                    }
                ],
                "racb": [
                    {
                        "id": "RACB-1",
                        "logType": "RACB",
                        "eventType": "ACTION_OPEN",
                        "eventTime": "2026-08-02T09:50:00+09:00",
                        "comment": "Pressure alarm 개선 조치",
                    }
                ],
            },
        )

        columns = context["contextEvents"]["columns"]
        rows = {
            row[columns.index("logType")]: row
            for row in context["contextEvents"]["rows"]
        }
        esop_row = rows["ESOP"]
        self.assertIsNone(esop_row[columns.index("eventType")])
        self.assertIsNone(esop_row[columns.index("status")])
        self.assertEqual(
            esop_row[columns.index("comment")],
            "sample wafer 검증 정상",
        )
        self.assertEqual(rows["CTTTM"][columns.index("eventType")], "CBM")
        self.assertIsNone(rows["RACB"][columns.index("eventType")])
        self.assertEqual(
            rows["RACB"][columns.index("comment")],
            "Pressure alarm 개선 조치",
        )

    def test_analysis_context_always_stays_within_prompt_budget(self) -> None:
        """원인과 TIP 그룹이 많아도 최종 context가 모델 입력 상한을 넘지 않습니다."""

        tip_logs = [
            {
                "id": f"TIP-{group_index}-{event_index}",
                "logType": "TIP",
                "eventType": f"L{group_index}_TIP",
                "eventTime": "2026-08-02T09:50:00+09:00",
                "lineId": "LINE-A",
                "process": f"PROC-{group_index}",
                "step": str(group_index),
                "ppid": f"PPID-{group_index}",
                "comment": f"원인-{event_index}-" + ("가" * 990),
            }
            for group_index in range(100)
            for event_index in range(30)
        ]

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["tip"],
            selected_tip_groups=["__ALL__"],
            logs_by_type={"tip": tip_logs},
        )

        serialized_context = json.dumps(
            context,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.assertLessEqual(len(serialized_context), MAX_PROMPT_CHARS)
        self.assertTrue(context["coverage"]["promptTruncated"])
        truncation = context["coverage"]["promptTruncation"]
        self.assertEqual(
            set(truncation),
            {
                "contextEvents",
                "targetEvents",
                "recordedCauses",
                "tipStatusStatistics",
                "eqpStatusStatistics",
            },
        )
        self.assertTrue(
            any(
                counts["after"] < counts["before"]
                for counts in truncation.values()
            )
        )
        messages = build_observer_analysis_messages(
            context=context,
            question="가" * 2400,
        )
        self.assertLessEqual(len(messages[1]["content"]), MAX_PROMPT_CHARS)

    def test_analysis_service_keeps_partial_source_failure_as_limitation(self) -> None:
        """부분 source 실패는 성공 응답을 유지하면서 분석 한계에 명시합니다."""

        def fetch_source(**kwargs):
            if kwargs["log_key"] == "eqp":
                raise RuntimeError("source failed")
            return []

        with (
            patch.object(
                selectors,
                "get_analysis_logs_by_type",
                side_effect=fetch_source,
            ),
            patch(
                "api.observer.services.analysis.stream_observer_analysis",
                return_value=[
                    '{"headline":"분석","summary":"요약","findings":[],'
                    '"recommendedChecks":[],"limitations":[]}'
                ],
            ),
        ):
            result = analyze_observer_logs_stream(
                eqp_id="EQP-ALPHA",
                start_at=self.start_at,
                end_at=self.end_at,
                log_types=["eqp", "tip"],
                selected_tip_groups=["__ALL__"],
                question="분석해 주세요.",
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(result["meta"]["sourceErrors"], {"eqp": "RuntimeError"})
        self.assertIn("eqp", result["analysis"]["limitations"][0])

    def test_analysis_limitation_names_the_reduced_prompt_sections(self) -> None:
        """prompt 축소 한계는 실제로 줄어든 section 이름을 반환합니다."""

        context = {
            "scope": {"eqpId": "EQP-ALPHA"},
            "targetEvents": [],
            "contextEvents": {"rows": []},
            "coverage": {
                "sourceMayBeTruncated": [],
                "sourceErrors": {},
                "promptTruncated": True,
                "promptTruncation": {
                    "contextEvents": {"before": 20, "after": 5},
                    "targetEvents": {"before": 2, "after": 2},
                },
            },
        }
        with (
            patch(
                "api.observer.services.analysis.build_observer_analysis_context",
                return_value=context,
            ),
            patch.object(selectors, "get_analysis_logs_by_type", return_value=[]),
            patch(
                "api.observer.services.analysis.stream_observer_analysis",
                return_value=[
                    '{"headline":"분석","summary":"요약","findings":[],'
                    '"recommendedChecks":[],"limitations":[]}'
                ],
            ),
        ):
            result = analyze_observer_logs_stream(
                eqp_id="EQP-ALPHA",
                start_at=self.start_at,
                end_at=self.end_at,
                log_types=["eqp"],
                selected_tip_groups=["__ALL__"],
                question="분석해 주세요.",
                cancellation=ExternalCallCancellation(),
            )

        self.assertIn("contextEvents", result["analysis"]["limitations"][0])
        self.assertNotIn("주변 로그 일부를 균등 축소", result["analysis"]["limitations"][0])

    def test_analysis_service_records_versions_and_filters_unknown_evidence(self) -> None:
        """실제 입력 근거만 유지하고 모델·프롬프트 버전을 metadata에 기록합니다."""

        config = ObserverOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
        )
        with (
            patch.object(
                selectors,
                "get_analysis_logs_by_type",
                return_value=[
                    {
                        "id": "EQP-DOWN-1",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                        "comment": "Pressure alarm",
                    },
                    {
                        "id": "EQP-DOWN-2",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:05:00+09:00",
                        "comment": "Pressure alarm",
                    }
                ],
            ),
            patch("api.observer.services.analysis_context.MAX_TARGET_EVENTS", 1),
            patch(
                "api.observer.services.analysis.ObserverOpenWebUIConfig.from_settings",
                return_value=config,
            ),
            patch(
                "api.observer.services.analysis.stream_observer_analysis",
                return_value=[
                    '{"headline":"분석","summary":"요약","findings":['
                    '{"category":"EQP","target":"DOWN","assessment":"반복",'
                    '"recordedCauses":[],"inferredCauses":[],"evidenceIds":'
                    '["EQP:EQP-DOWN-2","EQP:UNKNOWN"]}],'
                    '"recommendedChecks":[],"limitations":[]}'
                ],
            ),
        ):
            result = analyze_observer_logs_stream(
                eqp_id="EQP-ALPHA",
                start_at=self.start_at,
                end_at=self.end_at,
                log_types=["eqp"],
                selected_tip_groups=["__ALL__"],
                question="분석해 주세요.",
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(
            result["analysis"]["findings"][0]["evidenceIds"],
            ["EQP:EQP-DOWN-2"],
        )
        self.assertEqual(result["meta"]["analysisModel"], "gpt-oss-120b")
        self.assertEqual(
            result["meta"]["promptVersion"],
            "observer-analysis-prompt-v3",
        )
        self.assertEqual(result["meta"]["schemaVersion"], "observer-analysis-v1")

    def test_openwebui_request_reuses_config_and_medium_reasoning(self) -> None:
        """Observer 분석은 기존 OpenWebUI 설정과 medium reasoning을 사용합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"{\\"headline\\":\\"분석\\"}"}}]}',
            "data: [DONE]",
        ]
        session = Mock()
        session.post.return_value = response
        config = ObserverOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
            api_token="token",
            common_headers={"Send-System-Name": "Observer"},
            timeout_seconds=120,
        )

        content = "".join(
            stream_observer_analysis(
                messages=[{"role": "user", "content": "분석"}],
                cancellation=ExternalCallCancellation(),
                config=config,
                session=session,
            )
        )

        self.assertEqual(content, '{"headline":"분석"}')
        request = session.post.call_args
        self.assertEqual(request.kwargs["json"]["model"], "gpt-oss-120b")
        self.assertEqual(request.kwargs["json"]["reasoning_effort"], "medium")
        self.assertTrue(request.kwargs["json"]["stream"])
        self.assertTrue(request.kwargs["stream"])
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer token")
