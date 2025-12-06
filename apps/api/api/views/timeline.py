"""Dummy timeline endpoints used by the frontend timeline feature."""
from __future__ import annotations

from typing import Dict, List, Tuple

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

LINE_LIST: List[Dict[str, str]] = [
    {"id": "LINE-A", "name": "Line A"},
    {"id": "LINE-B", "name": "Line B"},
]

SDWT_MAP: Dict[str, List[Dict[str, str]]] = {
    "LINE-A": [
        {"id": "SD-10", "name": "SDWT-10"},
    ],
    "LINE-B": [
        {"id": "SD-20", "name": "SDWT-20"},
    ],
}

PRC_GROUPS: Dict[Tuple[str, str], List[Dict[str, str]]] = {
    ("LINE-A", "SD-10"): [
        {"id": "ETCH", "name": "PRC Group - Etch"},
        {"id": "CVD", "name": "PRC Group - CVD"},
    ],
    ("LINE-B", "SD-20"): [
        {"id": "TEST", "name": "PRC Group - Test"},
    ],
}

EQUIPMENTS: Dict[Tuple[str, str, str], List[Dict[str, str]]] = {
    ("LINE-A", "SD-10", "ETCH"): [
        {"id": "EQP-ALPHA", "name": "ALPHA-ETCH-01"},
        {"id": "EQP-BRAVO", "name": "BRAVO-ETCH-02"},
    ],
    ("LINE-A", "SD-10", "CVD"): [
        {"id": "EQP-CVD-01", "name": "CVD-LINEA-01"},
    ],
    ("LINE-B", "SD-20", "TEST"): [
        {"id": "EQP-TEST-01", "name": "TEST-HANDLER-01"},
    ],
}

EQUIPMENT_INFO: Dict[str, Dict[str, str]] = {
    "EQP-ALPHA": {
        "id": "EQP-ALPHA",
        "name": "ALPHA-ETCH-01",
        "lineId": "LINE-A",
        "sdwtId": "SD-10",
        "prcGroup": "ETCH",
    },
    "EQP-BRAVO": {
        "id": "EQP-BRAVO",
        "name": "BRAVO-ETCH-02",
        "lineId": "LINE-A",
        "sdwtId": "SD-10",
        "prcGroup": "ETCH",
    },
    "EQP-CVD-01": {
        "id": "EQP-CVD-01",
        "name": "CVD-LINEA-01",
        "lineId": "LINE-A",
        "sdwtId": "SD-10",
        "prcGroup": "CVD",
    },
    "EQP-TEST-01": {
        "id": "EQP-TEST-01",
        "name": "TEST-HANDLER-01",
        "lineId": "LINE-B",
        "sdwtId": "SD-20",
        "prcGroup": "TEST",
    },
}

LOGS: Dict[str, Dict[str, List[Dict[str, object]]]] = {
    "EQP-ALPHA": {
        "eqp": [
            {
                "id": "EQP-ALPHA-001",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T00:30:00Z",
                "endTime": "2024-07-15T02:30:00Z",
                "operator": "system",
                "comment": "Shift warm-up",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "EQP-ALPHA-002",
                "logType": "EQP",
                "eventType": "DOWN",
                "eventTime": "2024-07-15T02:30:00Z",
                "endTime": "2024-07-15T03:30:00Z",
                "operator": "ops1",
                "comment": "Vacuum low",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "EQP-ALPHA-003",
                "logType": "EQP",
                "eventType": "PM",
                "eventTime": "2024-07-15T03:30:00Z",
                "endTime": "2024-07-15T04:30:00Z",
                "operator": "maintenance",
                "comment": "Chamber clean",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "EQP-ALPHA-004",
                "logType": "EQP",
                "eventType": "IDLE",
                "eventTime": "2024-07-15T04:30:00Z",
                "endTime": "2024-07-15T05:30:00Z",
                "operator": "ops1",
                "comment": "Waiting for lot",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "EQP-ALPHA-005",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T05:30:00Z",
                "endTime": "2024-07-15T08:30:00Z",
                "operator": "system",
                "comment": "Lot processing",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
        ],
        "tip": [
            {
                "id": "TIP-ALPHA-001",
                "logType": "TIP",
                "eventType": "OPEN",
                "eventTime": "2024-07-15T01:00:00Z",
                "operator": "kim",
                "level": "MAJOR",
                "comment": "Opened chamber for clean",
                "url": "https://example.local/tip/TIP-ALPHA-001",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
                "process": "ETCH",
                "step": "STRIP",
                "ppid": "ALP-STRIP-01",
            },
            {
                "id": "TIP-ALPHA-002",
                "logType": "TIP",
                "eventType": "CLOSE",
                "eventTime": "2024-07-15T02:15:00Z",
                "operator": "kim",
                "level": "INFO",
                "comment": "Close after wipe down",
                "url": "https://example.local/tip/TIP-ALPHA-002",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
                "process": "ETCH",
                "step": "STRIP",
                "ppid": "ALP-STRIP-01",
            },
            {
                "id": "TIP-ALPHA-003",
                "logType": "TIP",
                "eventType": "OPEN",
                "eventTime": "2024-07-15T06:00:00Z",
                "operator": "lee",
                "level": "INFO",
                "comment": "Recipe load for pilot lot",
                "url": "https://example.local/tip/TIP-ALPHA-003",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
                "process": "ETCH",
                "step": "MAIN",
                "ppid": "ALP-ETCH-05",
            },
            {
                "id": "TIP-ALPHA-004",
                "logType": "TIP",
                "eventType": "CLOSE",
                "eventTime": "2024-07-15T07:45:00Z",
                "operator": "lee",
                "level": "MINOR",
                "comment": "Recipe completed",
                "url": "https://example.local/tip/TIP-ALPHA-004",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
                "process": "ETCH",
                "step": "MAIN",
                "ppid": "ALP-ETCH-05",
            },
        ],
        "ctttm": [
            {
                "id": "CTTTM-ALPHA-001",
                "logType": "CTTTM",
                "eventType": "TTM_WARN",
                "eventTime": "2024-07-15T03:45:00Z",
                "operator": "kim",
                "recipe": "ALP-ETCH-05",
                "comment": "Cycle time trending high",
                "duration": 12.5,
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "CTTTM-ALPHA-002",
                "logType": "CTTTM",
                "eventType": "TTM_FAIL",
                "eventTime": "2024-07-15T07:15:00Z",
                "operator": "lee",
                "recipe": "ALP-ETCH-05",
                "comment": "Exceeded target time",
                "duration": 18.2,
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
        ],
        "racb": [
            {
                "id": "RACB-ALPHA-001",
                "logType": "RACB",
                "eventType": "WARN",
                "eventTime": "2024-07-15T04:05:00Z",
                "operator": "monitor",
                "comment": "Carrier slowed near load port",
                "url": "https://example.local/racb/RACB-ALPHA-001",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "RACB-ALPHA-002",
                "logType": "RACB",
                "eventType": "ALARM",
                "eventTime": "2024-07-15T08:05:00Z",
                "operator": "monitor",
                "comment": "Interlock triggered on carrier",
                "url": "https://example.local/racb/RACB-ALPHA-002",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
        ],
        "jira": [
            {
                "id": "JIRA-ALPHA-001",
                "logType": "JIRA",
                "eventType": "ISSUED",
                "eventTime": "2024-07-15T05:10:00Z",
                "operator": "jira-bot",
                "issueKey": "TIMELINE-101",
                "assignee": "Alex",
                "priority": "High",
                "reporter": "QA",
                "summary": "Vacuum instability on ALPHA",
                "description": "Test lot aborted due to vacuum drop.",
                "url": "https://example.local/jira/TIMELINE-101",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
            {
                "id": "JIRA-ALPHA-002",
                "logType": "JIRA",
                "eventType": "CLOSED",
                "eventTime": "2024-07-15T09:00:00Z",
                "operator": "jira-bot",
                "issueKey": "TIMELINE-101",
                "assignee": "Alex",
                "priority": "High",
                "reporter": "QA",
                "summary": "Vacuum instability on ALPHA",
                "description": "Seal replaced and verified.",
                "url": "https://example.local/jira/TIMELINE-101",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            },
        ],
        "event": [
            {
                "id": "EVT-ALPHA-001",
                "logType": "EVENT",
                "eventType": "NOTE",
                "eventTime": "2024-07-15T01:45:00Z",
                "operator": "system",
                "comment": "Inline dummy event",
                "lineId": "LINE-A",
                "eqpId": "EQP-ALPHA",
            }
        ],
    },
    "EQP-BRAVO": {
        "eqp": [
            {
                "id": "EQP-BRAVO-001",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T00:50:00Z",
                "endTime": "2024-07-15T03:20:00Z",
                "operator": "system",
                "comment": "Production run",
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
            },
            {
                "id": "EQP-BRAVO-002",
                "logType": "EQP",
                "eventType": "IDLE",
                "eventTime": "2024-07-15T03:20:00Z",
                "endTime": "2024-07-15T04:00:00Z",
                "operator": "ops2",
                "comment": "Waiting for carrier",
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
            },
            {
                "id": "EQP-BRAVO-003",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T04:00:00Z",
                "endTime": "2024-07-15T07:00:00Z",
                "operator": "system",
                "comment": "Second lot",
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
            },
        ],
        "tip": [
            {
                "id": "TIP-BRAVO-001",
                "logType": "TIP",
                "eventType": "OPEN",
                "eventTime": "2024-07-15T02:10:00Z",
                "operator": "park",
                "level": "INFO",
                "comment": "Operator inspection",
                "url": "https://example.local/tip/TIP-BRAVO-001",
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
                "process": "ETCH",
                "step": "CHECK",
                "ppid": "BRV-CHECK-01",
            }
        ],
        "ctttm": [
            {
                "id": "CTTTM-BRAVO-001",
                "logType": "CTTTM",
                "eventType": "TTM_WARN",
                "eventTime": "2024-07-15T05:40:00Z",
                "operator": "park",
                "recipe": "BRV-ETCH-03",
                "comment": "Step running long",
                "duration": 10.1,
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
            }
        ],
        "racb": [],
        "jira": [
            {
                "id": "JIRA-BRAVO-001",
                "logType": "JIRA",
                "eventType": "ISSUED",
                "eventTime": "2024-07-15T06:00:00Z",
                "operator": "jira-bot",
                "issueKey": "TIMELINE-122",
                "assignee": "Morgan",
                "priority": "Medium",
                "reporter": "QA",
                "summary": "Intermittent carrier pause",
                "description": "Observed brief pause during unload sequence.",
                "url": "https://example.local/jira/TIMELINE-122",
                "lineId": "LINE-A",
                "eqpId": "EQP-BRAVO",
            }
        ],
        "event": [],
    },
    "EQP-CVD-01": {
        "eqp": [
            {
                "id": "EQP-CVD-01-001",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T01:10:00Z",
                "endTime": "2024-07-15T04:10:00Z",
                "operator": "system",
                "comment": "Baseline recipe",
                "lineId": "LINE-A",
                "eqpId": "EQP-CVD-01",
            },
            {
                "id": "EQP-CVD-01-002",
                "logType": "EQP",
                "eventType": "PM",
                "eventTime": "2024-07-15T04:10:00Z",
                "endTime": "2024-07-15T05:30:00Z",
                "operator": "maintenance",
                "comment": "Chamber clean",
                "lineId": "LINE-A",
                "eqpId": "EQP-CVD-01",
            },
        ],
        "tip": [],
        "ctttm": [],
        "racb": [],
        "jira": [],
        "event": [],
    },
    "EQP-TEST-01": {
        "eqp": [
            {
                "id": "EQP-TEST-01-001",
                "logType": "EQP",
                "eventType": "RUN",
                "eventTime": "2024-07-15T02:00:00Z",
                "endTime": "2024-07-15T04:00:00Z",
                "operator": "system",
                "comment": "Handler cycle",
                "lineId": "LINE-B",
                "eqpId": "EQP-TEST-01",
            }
        ],
        "tip": [],
        "ctttm": [],
        "racb": [],
        "jira": [],
        "event": [],
    },
}


def _normalize_id(value: str | None) -> str:
    return (value or "").strip().upper()


class TimelineLinesView(APIView):
    """Returns dummy line data."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(LINE_LIST, safe=False)


class TimelineSdwtView(APIView):
    """Returns SDWT list for a line."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = _normalize_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        return JsonResponse(SDWT_MAP.get(line_id, []), safe=False)


class TimelinePrcGroupView(APIView):
    """Returns PRC group list for a line/SDWT pair."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = _normalize_id(request.GET.get("lineId"))
        sdwt_id = _normalize_id(request.GET.get("sdwtId"))

        if not line_id or not sdwt_id:
            return JsonResponse({"error": "lineId and sdwtId are required"}, status=400)

        return JsonResponse(PRC_GROUPS.get((line_id, sdwt_id), []), safe=False)


class TimelineEquipmentsView(APIView):
    """Returns equipment list for a line/SDWT/PRC group."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = _normalize_id(request.GET.get("lineId"))
        sdwt_id = _normalize_id(request.GET.get("sdwtId"))
        prc_group = _normalize_id(request.GET.get("prcGroup"))

        if not line_id or not sdwt_id or not prc_group:
            return JsonResponse(
                {"error": "lineId, sdwtId, and prcGroup are required"}, status=400
            )

        return JsonResponse(EQUIPMENTS.get((line_id, sdwt_id, prc_group), []), safe=False)


class TimelineEquipmentInfoView(APIView):
    """Returns equipment metadata by eqpId, optionally scoped by line."""

    def get(
        self,
        request: HttpRequest,
        line_id: str | None = None,
        eqp_id: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        eqp_key = _normalize_id(eqp_id)
        if not eqp_key:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        info = EQUIPMENT_INFO.get(eqp_key)
        if not info:
            return JsonResponse({"error": "Equipment not found"}, status=404)

        if line_id and _normalize_id(line_id) != _normalize_id(info["lineId"]):
            return JsonResponse({"error": "Equipment not found for line"}, status=404)

        return JsonResponse(info)


class _TimelineLogsByTypeView(APIView):
    log_key: str = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        eqp_id = _normalize_id(request.GET.get("eqpId"))
        if not eqp_id:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        eqp_logs = LOGS.get(eqp_id, {})
        return JsonResponse(eqp_logs.get(self.log_key, []), safe=False)


class TimelineLogsView(_TimelineLogsByTypeView):
    """Returns merged logs for an equipment."""

    log_key = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        eqp_id = _normalize_id(request.GET.get("eqpId"))
        if not eqp_id:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        eqp_logs = LOGS.get(eqp_id, {})
        merged: List[Dict[str, object]] = []
        for key in ("eqp", "tip", "ctttm", "racb", "jira", "event"):
            merged.extend(eqp_logs.get(key, []))

        merged.sort(key=lambda log: str(log.get("eventTime") or ""))
        return JsonResponse(merged, safe=False)


class TimelineEqpLogsView(_TimelineLogsByTypeView):
    log_key = "eqp"


class TimelineTipLogsView(_TimelineLogsByTypeView):
    log_key = "tip"


class TimelineCtttmLogsView(_TimelineLogsByTypeView):
    log_key = "ctttm"


class TimelineRacbLogsView(_TimelineLogsByTypeView):
    log_key = "racb"


class TimelineJiraLogsView(_TimelineLogsByTypeView):
    log_key = "jira"
