# -*- coding: utf-8 -*-
"""지식 리소스 로더 — 룰·요건사실 카탈로그·서면 템플릿·검토 5축.

이 리소스들이 기록형 룰스킬의 '단일 정본'이다. 분산·중복 기술로 인한 드리프트를 막기 위해
여기 한 곳에 모은다(원본은 법학볼트 sync/_meta 의 여러 파일에 흩어져 있었음).
파일이 없으면 빈 기본값을 반환해 서버 기동은 막지 않는다(리소스 미배치 시 경고만).
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from .config import RESOURCES_DIR


def _read_text(name: str) -> str:
    p = RESOURCES_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _read_json(name: str) -> dict:
    p = RESOURCES_DIR / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


@functools.lru_cache(maxsize=None)
def load_rules() -> str:
    """R1~R10 + 논증·어법 규칙(정본 텍스트)."""
    return _read_text("rules.md")


@functools.lru_cache(maxsize=None)
def load_claim_catalog() -> dict:
    """청구권·범죄별 요건사실 카탈로그 (req 9 청구추출의 핵심 데이터)."""
    return _read_json("claim_catalog.json")


@functools.lru_cache(maxsize=None)
def load_brief_templates() -> dict:
    """서면유형별 골격(머리/본문단계/말미/필수/흔한누락/거울상)."""
    return _read_json("brief_templates.json")


@functools.lru_cache(maxsize=None)
def load_review_axes() -> dict:
    """논리·포섭 검토 5축 스키마."""
    return _read_json("review_axes.json")


def brief_template(brief_type: str) -> dict:
    """서면유형 → 골격. 거울상(mirror_of)만 정의된 경우 원본을 변환해 반환."""
    tpl = load_brief_templates()
    types = tpl.get("types", {})
    if brief_type in types:
        t = dict(types[brief_type])
        mo = t.get("mirror_of")
        if mo and mo in types and not t.get("body_skeleton"):
            base = types[mo]
            t["body_skeleton"] = base.get("body_skeleton", [])
            t["_mirrored_from"] = mo
        return t
    return {}


def claim_elements(claim_key: str) -> dict:
    """청구권/범죄 키 → 요건 리스트 + 증명책임 + 트리거 사실패턴."""
    cat = load_claim_catalog()
    for group in cat.get("groups", []):
        for item in group.get("claims", []):
            if item.get("key") == claim_key:
                return item
    return {}


def missing_resources() -> list[str]:
    """배치 안 된 리소스 목록(기동 시 경고용)."""
    want = ["rules.md", "claim_catalog.json", "brief_templates.json", "review_axes.json"]
    return [w for w in want if not (RESOURCES_DIR / w).exists()]
