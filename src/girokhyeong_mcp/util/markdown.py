# -*- coding: utf-8 -*-
"""마크다운/프론트매터/페이지마커 헬퍼.

OCR 출력 계약(법학볼트 ocr_extract_v3 와 동일): 프론트매터 + `<!-- p.N -->` 페이지마커 +
`{prefix}_p{NNN}-{MMM}.md` 파일명. 이 계약으로 다운스트림이 인용 페이지를 역추적한다(R3·#14).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable

PAGE_MARK_RE = re.compile(r"<!--\s*p\.(\d+)\s*-->")


def page_marker(n: int) -> str:
    return f"<!-- p.{n} -->"


def assemble_pages(pages: Iterable[tuple[int, str]]) -> str:
    """[(page_no, text), ...] → '<!-- p.N -->\\n\\n{text}' 들을 빈 줄로 join."""
    return "\n\n".join(f"{page_marker(n)}\n\n{(t or '').strip()}" for n, t in pages)


def split_pages(body: str) -> list[tuple[int, str]]:
    """페이지마커 기준으로 본문을 (page_no, text) 리스트로 역분해."""
    out: list[tuple[int, str]] = []
    parts = PAGE_MARK_RE.split(body)
    # split 결과: [pre, n1, text1, n2, text2, ...]
    it = iter(parts[1:])
    for n, t in zip(it, it):
        out.append((int(n), t.strip()))
    return out


def ocr_frontmatter(*, book: str, author: str, subject: str, start: int, end: int,
                    source: str, engine_label: str, caveat: str,
                    extracted: str | None = None) -> str:
    """OCR 청크 프론트매터 (다운스트림 무변경 계약)."""
    extracted = extracted or _dt.date.today().isoformat()
    tags = f"[교재원문, {subject}, {author}_{book}]" if author else f"[사건기록, {subject}]"
    return (
        "---\n"
        f"tags: {tags}\n"
        f"문서: 《{book}》" + (f" ({author})" if author else "") + "\n"
        f"과목: {subject}\n"
        f"포함_페이지: {start}-{end}\n"
        f"저자: {author}\n"
        f"출처: {source}\n"
        f"추출일: {extracted}\n"
        f"추출엔진: {engine_label}\n"
        f"교정상태: {caveat}, Claude 교정 + law_api verify-text 검증 필요\n"
        "---\n"
    )


def stage_frontmatter(*, stage: str, brief_type: str | None, party_side: str | None,
                      case_id: str, source_files: list[str] | None = None,
                      posture: str | None = None) -> str:
    """단계 산출물 프론트매터 — 자세-스탬프(연구 N4: '경고는 잊히고 게이트는 박힌다') 영속화.

    posture: 이 단계에서 내린 핵심 결정(예: 당사자 입장 확정 사유, 다툼없음 전제 등)을
    frontmatter 에 박아 다음 세션에 회귀하지 않게 한다.
    """
    today = _dt.date.today().isoformat()
    lines = ["---", f"단계: {stage}", f"사건ID: {case_id}", f"생성일: {today}"]
    if brief_type:
        lines.append(f"서면유형: {brief_type}")
    if party_side:
        lines.append(f"당사자입장: {party_side}")
    if posture:
        lines.append(f"확정자세: {posture}")
    if source_files:
        lines.append("출처파일:")
        lines += [f"  - {p}" for p in source_files]
    lines.append("검증상태: 미검증  # law_api verify-text + 논리포섭 5축 통과 시 갱신")
    lines.append("---")
    return "\n".join(lines) + "\n"
