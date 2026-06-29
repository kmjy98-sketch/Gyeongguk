# -*- coding: utf-8 -*-
"""정확성 검증 — 산출물의 조문·사건번호 실재 일괄검증(law_api) + 제출 전 체크리스트.

논증(요건→포섭→결론) 검토는 별도 축(review_axes, LLM 의미판단). 여기서는 '진위(실재)'만.
"""
from __future__ import annotations

import os

from .. import config, law_api

# 제출 전 체크리스트 (독립판 §8 + 가인 E절)
CHECKLIST = [
    "인용 판례·조문 전건 검증(검증 불가분은 [검증필요]로 남겼는가)",
    "직접 인용부(\"…\")가 원문의 연속된 부분 그대로인가",
    "금액·날짜·항 번호가 기록과 일치(합계액은 구성까지)",
    "공부상 상태와 모순되는 용어가 없는가(지목 '답'을 '나대지'로 부르지 않음)",
    "모든 문장의 주어-술어 호응 확인(무주어 술어 없음)",
    "실측 면수가 제한 이내인가(본문+각주 합산, 표지·별지 우회 금지)",
    "작성 명의·날짜·파일명이 지시문 형식과 글자 단위로 일치",
    "상대방 최강 논거에 대한 반박이 들어 있는가(R9)",
    "인용 판례마다 사건번호 병기 + 원문 표현 확인",
    "불리판례 최소 1건의 구별(distinguishing) 논증이 있는가",
    "모든 법리에 사실관계 포섭 문장이 붙어 있는가(포섭 강제)",
]


def verify_brief(text_or_path: str) -> dict:
    """서면(또는 매트릭스) 텍스트의 조문·사건번호 실재 일괄검증 + 게이트 판정."""
    text = text_or_path
    if os.path.isfile(text_or_path):
        with open(text_or_path, encoding="utf-8") as fh:
            text = fh.read()

    vt = law_api.verify_text(text)
    unverified = vt.get("unverified", [])
    # 게이트: 키/네트워크 부재(검증 자체 불가) → '키없음'을 '보류'와 구별
    if not config.law_api_key() or vt.get("api_error"):
        gate = "키없음"
    elif unverified:
        gate = "보류"  # 미검증 인용 존재 → 본문 인용 강등 필요
    else:
        gate = "통과"

    return {
        "summary": vt.get("summary"),
        "case_results": vt.get("case_results"),
        "article_results": vt.get("article_results"),
        "unverified": unverified,
        "gate": gate,   # 통과 | 보류 | 키없음
        "지침": (
            "unverified 에 뜬 조문·사건번호가 걸린 단정은 본문 직접인용에서 내리고 "
            "[검증필요: 후보 없음] 또는 [부분검증: 사건명만 일치, 판시 미확인]으로 강등한다. "
            "검증완료(통과)만 본문 따옴표 직접인용 승격(R3·R4)."
        ),
        "제출전_체크리스트": CHECKLIST,
    }
