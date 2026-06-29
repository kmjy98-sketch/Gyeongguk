# -*- coding: utf-8 -*-
"""한자→한글 변환 (룰 R7 / 독립판 §19). 당사자 약칭·기본 법률 한자만 보수적으로 치환한다.

주의: 사건번호·법령명 등 anchor 의 한자는 함부로 바꾸지 않는다(여기 매핑은 당사자/기초 용어 한정).
변환은 LLM 산출 본문의 후처리 보조용이며, 의미 판단이 필요한 한자는 LLM이 처리한다.
"""
from __future__ import annotations

# 당사자 약칭 (기록형 빈출) — 단독 글자 치환
PARTY_MAP = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정",
    "戊": "무", "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}

# 기초 법률 용어 한자 (단독·접사)
TERM_MAP = {
    "條": "조", "項": "항", "號": "호", "目": "목",
    "原告": "원고", "被告": "피고", "被疑者": "피의자", "被告人": "피고인",
    "證": "증", "甲第": "갑 제", "乙第": "을 제",
}

_ALL = {**PARTY_MAP, **TERM_MAP}


def to_hangul(text: str, *, parties_only: bool = False) -> str:
    """본문 한자를 보수적으로 한글로 치환. parties_only=True 면 당사자 약칭(甲乙丙丁…)만."""
    if not text:
        return text
    table = PARTY_MAP if parties_only else _ALL
    # 긴 키 먼저 치환(원告 → 원고 같은 복합 우선)
    for k in sorted(table, key=len, reverse=True):
        if k in text:
            text = text.replace(k, table[k])
    return text


def has_hanja(text: str) -> bool:
    """CJK 한자 포함 여부 (검토 게이트 경고용)."""
    return any("一" <= ch <= "鿿" for ch in (text or ""))
