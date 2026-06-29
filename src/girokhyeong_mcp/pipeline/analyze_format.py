# -*- coding: utf-8 -*-
"""양식 역분석 (req 4: '작성 양식은 주어진 양식 분석해서').

사용자가 제공한 양식/샘플 서면(docx·pdf·md·txt·hwp 미리보기)을 읽어 구조 특징을 추출한다:
머리 정형 · 제목(자간 띄움) · 본문 번호체계 · 말미(작성명의/날짜/수신법원) · 인용 형식 · 섹션 헤딩.
이 구조를 draft 단계가 따른다. 양식 미제공 시 draft 는 내장 brief_templates 로 폴백한다.
"""
from __future__ import annotations

import re
from pathlib import Path

# 제목 후보: '변 론 요 지 서', '준 비 서 면', '의 견 서', '참 고 서 면' 등 자간 띄움
_TITLE_RE = re.compile(r"^\s*([가-힣])(\s[가-힣])+\s*$")
_CASE_CITE_RE = re.compile(r"(대법원|헌법재판소|[가-힣]+지방법원)\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*(선고|자)?\s*\d{2,4}[가-힣]+\d+")
_ART_CITE_RE = re.compile(r"「?[가-힣]{2,12}법」?\s*제\s*\d+\s*조")
_NUM_PATTERNS = {
    "1.": re.compile(r"^\s*\d+\.\s"),
    "가.": re.compile(r"^\s*[가-힣]\.\s"),
    "1)": re.compile(r"^\s*\d+\)\s"),
    "가)": re.compile(r"^\s*[가-힣]\)\s"),
    "①": re.compile(r"^\s*[①-⑮]"),
    "Ⅰ.": re.compile(r"^\s*[Ⅰ-Ⅻ]\.\s"),
}
_TAIL_HINTS = ("귀중", "변호사", "검사", "소송대리인", "법무법인", "담당변호사")
_HEAD_HINTS = ("위 사건에 관하여", "다음과 같이", "변론합니다", "의견을 제출합니다", "준비합니다", "보충합니다")


def _read_any(path: str) -> str:
    p = Path(path)
    suf = p.suffix.lower()
    if suf in (".md", ".txt"):
        return p.read_text(encoding="utf-8", errors="replace")
    if suf == ".docx":
        try:
            import docx
            return "\n".join(par.text for par in docx.Document(str(p)).paragraphs)
        except Exception as e:
            return f"[docx 읽기 실패: {e}]"
    if suf == ".pdf":
        try:
            from .parse import extract_pymupdf, page_count
            pages = extract_pymupdf(str(p), 1, min(page_count(str(p)), 60))
            return "\n".join(t for _, t in pages)
        except Exception as e:
            return f"[pdf 읽기 실패: {e}]"
    if suf in (".hwp", ".hwpx"):
        try:
            import olefile
            if olefile.isOleFile(str(p)):
                ole = olefile.OleFileIO(str(p))
                if ole.exists("PrvText"):
                    return ole.openstream("PrvText").read().decode("utf-16-le", "replace")
        except Exception as e:
            return f"[hwp 미리보기 실패: {e} — 한글에서 txt/pdf 로 내보낸 뒤 분석 권장]"
    return p.read_text(encoding="utf-8", errors="replace")


def analyze_format(path: str) -> dict:
    """양식 파일 → 구조 특징 dict."""
    text = _read_any(path)
    lines = [ln.rstrip() for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln.strip()]

    def _strip_md(ln: str) -> str:          # 마크다운 헤딩(##)·강조(**) 마커 제거 후 평가
        return re.sub(r"^#{1,6}\s*", "", ln.strip()).replace("**", "").strip()

    titles = [_strip_md(ln) for ln in nonempty[:30] if _TITLE_RE.match(_strip_md(ln))]
    head = [_strip_md(ln) for ln in nonempty[:40] if any(h in ln for h in _HEAD_HINTS)]
    tail = [_strip_md(ln) for ln in nonempty[-40:] if any(h in ln for h in _TAIL_HINTS)]

    numbering = [name for name, rx in _NUM_PATTERNS.items() if any(rx.match(ln) for ln in lines)]
    case_cites = _CASE_CITE_RE.findall(text)
    art_cites = sorted(set(_ART_CITE_RE.findall(text)))

    # 섹션 헤딩 후보(번호로 시작하는 줄)
    headings = [ln.strip() for ln in nonempty
                if any(rx.match(ln) for rx in _NUM_PATTERNS.values())][:40]

    return {
        "원본": Path(path).name,
        "제목양식": titles,                       # 예: ['의 견 서']
        "머리정형": head,
        "말미정형": tail,
        "번호체계": numbering,                    # 예: ['1.','가.','1)','①']
        "인용_판례형식_샘플": [" ".join(c if isinstance(c, str) else c[0] for c in case_cites[:5])] if case_cites else [],
        "인용_조문형식_샘플": art_cites[:8],
        "섹션헤딩_샘플": headings,
        "지침": "draft 단계는 위 제목양식·머리/말미정형·번호체계·인용형식을 그대로 따른다. "
                "양식에 없는 항목만 내장 brief_templates 로 보완한다.",
    }
