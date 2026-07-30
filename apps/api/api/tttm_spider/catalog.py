# =============================================================================
# 모듈: TTTM Spider 카테고리 카탈로그 (MOCK — 데모/드릴다운 테스트용)
# 원본: catalog.py (미확보). 대시보드가 쓰는 심볼을 그대로 노출한다:
#   LEAF_ORDER / TOP_ORDER / CATEGORY_TREE / LEAF_LABEL / TOP_LABEL /
#   leaf_parent() / load_sensor_category_map() / load_oes_wavelength_catalog()
#
# ⚠ MOCK: 실제 catalog.py 와 sensor_catalog_map.txt(도메인 데이터)가 아직 없어서,
#   드릴다운(top→leaf→sensor)을 브라우저에서 끝까지 테스트할 수 있도록 임시 다축
#   트리를 넣었다. sensor_catalog_map.txt 의 센서명도 mock 파이프라인이 만드는
#   param 이름에 맞춘 것이다. 실제 파일을 받으면 이 파일 + 맵을 교체할 것.
#   (CATALOG_IS_STUB=True 로 프론트/메타에 "stub" 표시)
#
# OES 파장→화학종 카탈로그(oes_wavelength_catalog.txt)는 확보되어 여기서 로드한다.
# =============================================================================
from __future__ import annotations

import math
import os

# ── TRACE 카테고리 트리 (MOCK 다축) ─────────────────────────────────────────
# top → [leaf...]
CATEGORY_TREE: dict[str, list[str]] = {
    "RF": ["RF_FWD", "RF_REF"],
    "PRESSURE": ["PRESS"],
    "GAS": ["GAS_AR", "GAS_O2"],
    "ESC": ["ESC_V"],
    "ENDPOINT": ["HE_LEAK"],
    "ETC": ["ETC"],  # 맵에 없는 센서 폴백
}
TOP_ORDER: list[str] = ["RF", "PRESSURE", "GAS", "ESC", "ENDPOINT", "ETC"]
LEAF_ORDER: list[str] = ["RF_FWD", "RF_REF", "PRESS", "GAS_AR", "GAS_O2", "ESC_V", "HE_LEAK", "ETC"]
TOP_LABEL: dict[str, str] = {
    "RF": "RF Power", "PRESSURE": "Pressure", "GAS": "Gas Flow",
    "ESC": "ESC", "ENDPOINT": "Endpoint", "ETC": "ETC",
}
LEAF_LABEL: dict[str, str] = {
    "RF_FWD": "RF Fwd", "RF_REF": "RF Ref", "PRESS": "Chamber Press",
    "GAS_AR": "Ar Flow", "GAS_O2": "O2 Flow", "ESC_V": "ESC Volt",
    "HE_LEAK": "He Leak", "ETC": "ETC",
}
_LEAF_TO_PARENT: dict[str, str] = {
    leaf: top for top, leaves in CATEGORY_TREE.items() for leaf in leaves
}

_DEFAULT_SENSOR_MAP_PATH = os.path.join(os.path.dirname(__file__), "sensor_catalog_map.txt")
_DEFAULT_OES_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "oes_wavelength_catalog.txt")

CATALOG_IS_STUB = True   # MOCK 카탈로그로 동작 중임을 프론트/메타에 표시


def leaf_parent(leaf: str) -> str:
    """원본 catalog.leaf_parent: leaf 의 상위 top. 미매핑이면 자기 자신."""
    return _LEAF_TO_PARENT.get(leaf, leaf)


def load_sensor_category_map(path: str | None = None) -> dict[str, str]:
    """
    원본 catalog.load_sensor_category_map: 'sensor,category' 텍스트를 dict 로.
    (# 주석/빈 줄 무시). 파일이 없으면 빈 dict → 모든 센서가 ETC 로 폴백된다.
    """
    p = path or _DEFAULT_SENSOR_MAP_PATH
    out: dict[str, str] = {}
    if not os.path.exists(p):
        return out
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2 or not parts[0]:
                continue
            out[parts[0]] = parts[1] or "ETC"
    return out


def load_oes_wavelength_catalog(path: str | None = None) -> list[tuple[float, float, str, str]]:
    """
    원본 tttm_dashboard_api._load_oes_wavelength_catalog 이식.
    'low,high,category_key,category_label' → [(low, high, key, label), ...].
    파일이 없거나 파싱 실패하면 빈 리스트(=전부 ETC 로 분류)로 폴백.
    """
    p = path or _DEFAULT_OES_CATALOG_PATH
    ranges: list[tuple[float, float, str, str]] = []
    if not os.path.exists(p):
        return ranges
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                low = float(parts[0])
                high = float(parts[1])
                key = parts[2]
                label = parts[3] if len(parts) > 3 and parts[3] else key
            except ValueError:
                continue
            if not math.isfinite(low) or not math.isfinite(high):
                continue
            ranges.append((low, high, key, label))
    return ranges
