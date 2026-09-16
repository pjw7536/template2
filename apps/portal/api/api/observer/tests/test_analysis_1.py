from . import *  # noqa: F403


class ObserverAnalysisPart1Tests(TestCase):
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

    def test_analysis_question_accepts_and_preserves_2400_characters(self) -> None:
        """분석 질문 2,400자를 검증과 OpenWebUI 입력에서 동일하게 보존합니다."""

        question = "가" * 2400
        messages = build_observer_analysis_messages(
            context={},
            question=question,
            conversation_summary="이전 분석에서 DOWN 원인을 확인했습니다.",
        )
        self.assertIn(question, messages[1]["content"])
        self.assertIn("이전 분석에서 DOWN 원인을 확인했습니다.", messages[1]["content"])

    def test_analysis_prompt_requires_synthesized_findings(self) -> None:
        """system prompt가 종합 분석과 한국어 답변을 우선하는지 확인합니다."""

        self.assertIn("단순 건수나 comment를 나열하지 말고", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("운영상 의미", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("chronologicalSummary", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("독립된 raw 근거", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "EQP 로그는 설비가 wafer를 진행할 수 있는 상태인지",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn("DOWN은 설비에 interlock 또는 error", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("LOCAL은 사용자가 설비를 offline", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("RUN은 설비에서 wafer가 진행 중", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("IDLE은 설비가 진행 가능한 상태", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("PM은 Preventive Maintenance", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "TIP 로그는 설비 자체의 사용 가능 상태와 별개",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "L1_TIP은 Etch기술팀이 관리하는 권한",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Process Integration이나 Defect관리그룹이 더 높은 권한",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn("L1_TIP보다 무거운 제한", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("L3_TIP은 비표준 설비에 적용된 TIP", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "숫자만으로 L2_TIP보다 더 무거운 제한이라고 추정하지",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn("TIP_RELEASE에 따른 열림 상태", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "TIP 닫힘만으로 설비 자체가 DOWN 또는 사용 불가능하다고 판단하지",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "생산된 wafer의 계측 데이터에서 발생한 interlock",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "wafer를 생산하는 동안 설비 sensor의 이상점을 감지",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "점검 또는 이상 발생 시 엔지니어가 점검 이력과 history를 기록",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "PM 이후 설비 backup을 통해 설비를 다시 가동",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn("CBM은 정해진 시간에 따른 정기 점검", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("NSP는 비정기 점검", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("MWO는 문제 발생 또는 기록 목적", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "sample wafer를 보내 설비를 검증한 이력",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "row의 title이 comment로 전달",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn(
            "설비 파츠의 개선품 또는 원가절감 목적의 개선품을 평가한 history",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertIn("사실 근거가 아닙니다", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("findings는 중요도 순으로 최대 5개", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn(
            "사용자에게 표시되는 문장은 되도록이면 한국어로 작성하되",
            ANALYSIS_SYSTEM_PROMPT,
        )
        self.assertEqual(
            OBSERVER_ANALYSIS_PROMPT_VERSION,
            "observer-analysis-prompt-v3",
        )

    def test_analysis_result_limits_findings_to_five(self) -> None:
        """모델이 많은 finding을 반환해도 사용자 분석 상한을 보장합니다."""

        result = normalize_observer_analysis_result(
            {
                "findings": [
                    {
                        "category": "EQP",
                        "target": f"상태-{index}",
                        "assessment": f"분석-{index}",
                    }
                    for index in range(6)
                ]
            }
        )

        self.assertEqual(len(result["findings"]), 5)
        self.assertEqual(result["findings"][-1]["assessment"], "분석-4")

    def test_analysis_selector_prefilters_large_status_sources(self) -> None:
        """EQP/TIP 제외 상태가 분석 조회 상한을 차지하지 않게 DB filter를 전달합니다."""

        with (
            patch(
                f"{OBSERVER_LOG_SELECTORS}.eqp_status_chg_selectors.fetch_eqp_timeline_logs",
                return_value=[],
            ) as eqp_selector,
            patch(
                f"{OBSERVER_LOG_SELECTORS}.mi_tip_update_hist_selectors.fetch_tip_timeline_logs",
                return_value=[],
            ) as tip_selector,
        ):
            selectors.get_analysis_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                start_at=self.start_at,
                end_at=self.end_at,
                limit=5000,
            )
            selectors.get_analysis_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="tip",
                start_at=self.start_at,
                end_at=self.end_at,
                limit=5000,
            )

        self.assertEqual(
            eqp_selector.call_args.kwargs["statuses"],
            ("DOWN", "IDLE", "LOCAL"),
        )
        self.assertEqual(
            tip_selector.call_args.kwargs["event_type_pattern"],
            r"^L.*_TIP$",
        )

    def test_analysis_evidence_selector_returns_matching_stable_id(self) -> None:
        """근거 selector는 분석 source의 stable event ID로 한 건을 복원합니다."""

        logs = [
            {"id": "EQP-99", "logType": "EQP"},
            {"id": "EQP-100", "logType": "EQP", "comment": "근거"},
        ]
        with patch(
            f"{OBSERVER_LOG_SELECTORS}.get_analysis_logs_by_type",
            return_value=logs,
        ) as source:
            result = selectors.get_analysis_evidence_log(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                evidence_id="EQP:EQP-100",
                start_at=self.start_at,
                end_at=self.end_at,
            )

        self.assertEqual(result, logs[1])
        source.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_key="eqp",
            start_at=self.start_at,
            end_at=self.end_at,
            limit=5000,
        )

    def test_analysis_context_filters_eqp_and_tip_target_statuses(self) -> None:
        """정상 EQP와 DOING/CNT TIP은 분석 대상에서 제외합니다."""

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["eqp", "tip", "spc-interlock"],
            selected_tip_groups=["__ALL__"],
            logs_by_type={
                "eqp": [
                    {
                        "id": "EQP-RUN",
                        "logType": "EQP",
                        "eventType": "RUN",
                        "eventTime": "2026-08-02T09:00:00+09:00",
                        "comment": "정상 가동",
                    },
                    {
                        "id": "EQP-DOWN",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                        "comment": "Pressure alarm 점검",
                    },
                ],
                "tip": [
                    {
                        "id": "TIP-DOING",
                        "logType": "TIP",
                        "eventType": "DOING",
                        "eventTime": "2026-08-02T09:40:00+09:00",
                    },
                    {
                        "id": "TIP-CNT",
                        "logType": "TIP",
                        "eventType": "CNT",
                        "eventTime": "2026-08-02T09:45:00+09:00",
                    },
                    {
                        "id": "TIP-L1",
                        "logType": "TIP",
                        "eventType": "L1_TIP",
                        "eventTime": "2026-08-02T09:50:00+09:00",
                        "lineId": "LINE-A",
                        "process": "PROC-A",
                        "step": "1200",
                        "ppid": "PPID-1",
                        "comment": "Pressure 확인 필요",
                    },
                ],
                "spc-interlock": [
                    {
                        "id": "SPC_ITL:1",
                        "logType": "SPC_ITL",
                        "eventType": "INT-1",
                        "eventTime": "2026-08-02T09:55:00+09:00",
                        "metroItem": "PRESSURE_HIGH",
                        "comment": "Spec out",
                    },
                    {
                        "id": "SPC_ITL:2",
                        "logType": "SPC_ITL",
                        "eventType": "INT-2",
                        "eventTime": "2026-08-02T20:00:00+09:00",
                        "metroItem": "TEMP_HIGH",
                    },
                ],
            },
        )

        self.assertEqual(context["eqpStatusStatistics"][0]["status"], "DOWN")
        self.assertEqual(context["eqpStatusStatistics"][0]["count"], 1)
        self.assertEqual(context["tipStatusStatistics"][0]["status"], "L1_TIP")
        self.assertEqual(context["tipStatusStatistics"][0]["count"], 1)
        context_rows = context["contextEvents"]["rows"]
        self.assertEqual(len(context_rows), 1)
        self.assertEqual(context_rows[0][2], "SPC_ITL")
        self.assertEqual(context["coverage"]["eqpTargetCount"], 1)
        self.assertEqual(context["coverage"]["tipTargetCount"], 1)

    def test_analysis_context_uses_eqp_comment_before_first_delimiter(self) -> None:
        """EQP 기록 원인은 첫 !@! 앞부분만 사용해 집계합니다."""

        context = build_observer_analysis_context(
            eqp_id="EQP-ALPHA",
            start_at=self.start_at,
            end_at=self.end_at,
            log_types=["eqp"],
            selected_tip_groups=["__ALL__"],
            logs_by_type={
                "eqp": [
                    {
                        "id": "EQP-DOWN-1",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T10:00:00+09:00",
                        "comment": "Pressure alarm !@! 작업자 메모 !@! 추가 정보",
                    },
                    {
                        "id": "EQP-DOWN-2",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T11:00:00+09:00",
                        "comment": "Pressure alarm!@!다른 메모",
                    },
                    {
                        "id": "EQP-DOWN-3",
                        "logType": "EQP",
                        "eventType": "DOWN",
                        "eventTime": "2026-08-02T12:00:00+09:00",
                        "comment": "구분자 없는 원인",
                    },
                ]
            },
        )

        causes = context["eqpStatusStatistics"][0]["recordedCauses"]
        self.assertEqual(
            [(cause["comment"], cause["count"]) for cause in causes],
            [("Pressure alarm", 2), ("구분자 없는 원인", 1)],
        )
        self.assertEqual(
            [event["comment"] for event in context["targetEvents"]],
            ["Pressure alarm", "Pressure alarm", "구분자 없는 원인"],
        )
