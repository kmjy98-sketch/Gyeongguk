# -*- coding: utf-8 -*-
"""파싱(OCR/추출) 단계 — req 6: opendataloader-pdf 주 엔진, pymupdf/pdfplumber 폴백.

엔진 어댑터 계약(법학볼트 ocr_extract_v3 승계):
    extract(pdf_path, start, end) -> list[(page_no:int(1-based 절대), text:str)]

출력 계약: `{prefix}_p{NNN}-{MMM}.md` 청크 파일 (프론트매터 + `<!-- p.N -->` 페이지마커).
재개: 기존 출력 파일이 RESUME_MIN_BYTES 초과면 스킵.

opendataloader-pdf 는 Java 11+ 가 PATH 에 있어야 한다(코어가 Java). 없으면 자동으로
pymupdf(디지털 텍스트레이어) 폴백. 스캔 PDF(텍스트 빈약)는 opendataloader hybrid OCR 또는
경고로 처리한다.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..util import markdown as md

# ── 엔진 가용성 탐지 ─────────────────────────────────────────


def java_available() -> bool:
    return shutil.which("java") is not None


def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def opendataloader_available() -> bool:
    return _has("opendataloader_pdf") and java_available()


# ── PDF 페이지 분리 어댑터 (fitz) ────────────────────────────


def _open_doc(pdf_path: str):
    import fitz  # PyMuPDF
    return fitz.open(pdf_path)


def page_count(pdf_path: str) -> int:
    doc = _open_doc(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def subset_pdf(pdf_path: str, start: int, end: int) -> str:
    """start~end(1-based 포함) 페이지만 떼낸 임시 PDF 경로."""
    import fitz
    src = fitz.open(pdf_path)
    try:
        nd = fitz.open()
        nd.insert_pdf(src, from_page=start - 1, to_page=end - 1)
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        nd.save(path)
        nd.close()
        return path
    finally:
        src.close()


# ── 엔진들 ───────────────────────────────────────────────────


class EngineUnavailable(RuntimeError):
    pass


def extract_pymupdf(pdf_path: str, start: int, end: int) -> list[tuple[int, str]]:
    """디지털 텍스트레이어 추출(폴백, Java 불요). 스캔 PDF 는 빈 텍스트가 나온다."""
    import fitz
    doc = fitz.open(pdf_path)
    try:
        out = []
        for i in range(start - 1, min(end, doc.page_count)):
            out.append((i + 1, (doc[i].get_text("text") or "").strip()))
        return out
    finally:
        doc.close()


def extract_pdfplumber(pdf_path: str, start: int, end: int) -> list[tuple[int, str]]:
    try:
        import pdfplumber
    except Exception as e:
        raise EngineUnavailable("pdfplumber 미설치: %s" % e)
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(start - 1, min(end, len(pdf.pages))):
            out.append((i + 1, (pdf.pages[i].extract_text() or "").strip()))
    return out


def extract_opendataloader(pdf_path: str, start: int, end: int) -> list[tuple[int, str]]:
    """opendataloader-pdf 로 추출 → 페이지별 마크다운.

    청크 subset PDF 를 JSON+markdown 으로 변환하고, JSON 의 페이지 정보로 페이지별 묶음.
    JSON 스키마가 예상과 다르면 markdown 전체를 시작 페이지 블록으로 폴백한다.
    hybrid(스캔 OCR)는 config.GIROK_ODL_HYBRID 가 있으면 사용.
    """
    try:
        import opendataloader_pdf  # noqa
    except Exception as e:
        raise EngineUnavailable("opendataloader_pdf 미설치: %s" % e)
    if not java_available():
        raise EngineUnavailable("Java 11+ 가 PATH 에 없음 (opendataloader 코어는 Java). Adoptium 설치 필요.")

    sub = subset_pdf(pdf_path, start, end)
    out_dir = tempfile.mkdtemp(prefix="odl_")
    try:
        kwargs = dict(input_path=[sub], output_dir=out_dir, format="json,markdown")
        hy = config.odl_hybrid_url()
        if hy:
            kwargs["hybrid"] = hy
        opendataloader_pdf.convert(**kwargs)
        pages = _read_odl_output(out_dir, base_page=start, n_pages=end - start + 1)
        return pages
    finally:
        for p in (sub,):
            try:
                os.unlink(p)
            except OSError:
                pass
        shutil.rmtree(out_dir, ignore_errors=True)


def _read_odl_output(out_dir: str, base_page: int, n_pages: int) -> list[tuple[int, str]]:
    """opendataloader 출력 폴더에서 페이지별 텍스트를 복원. JSON 우선, 실패 시 markdown 폴백."""
    import json
    odir = Path(out_dir)
    jsons = list(odir.rglob("*.json"))
    if jsons:
        try:
            data = json.loads(jsons[0].read_text(encoding="utf-8"))
            grouped = _group_json_by_page(data)
            if grouped:
                # base_page 가 1이면 subset 의 1페이지 = 절대 base_page
                return [(base_page + (pg - 1), txt) for pg, txt in sorted(grouped.items())]
        except Exception:
            pass
    mds = list(odir.rglob("*.md")) or list(odir.rglob("*.markdown"))
    if mds:
        whole = mds[0].read_text(encoding="utf-8").strip()
        return [(base_page, whole)]
    return [(base_page, "")]


def _group_json_by_page(data) -> dict[int, str]:
    """opendataloader JSON 요소들을 page 인덱스로 묶어 페이지별 텍스트 생성(스키마 방어적)."""
    elements = None
    if isinstance(data, dict):
        for k in ("elements", "content", "blocks", "items", "children"):
            if isinstance(data.get(k), list):
                elements = data[k]
                break
    elif isinstance(data, list):
        elements = data
    if not elements:
        return {}

    by_page: dict[int, list[str]] = {}

    def page_of(el) -> int:
        for k in ("page", "page_number", "pageNumber", "page_index", "pageIndex"):
            v = el.get(k) if isinstance(el, dict) else None
            if isinstance(v, int):
                return v if k.endswith("number") or k == "page" else v + 1
        return 1

    def text_of(el) -> str:
        if isinstance(el, dict):
            for k in ("text", "markdown", "content", "value"):
                v = el.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""

    def walk(el):
        if isinstance(el, dict):
            t = text_of(el)
            if t:
                by_page.setdefault(page_of(el), []).append(t)
            for k in ("children", "elements", "content", "blocks"):
                if isinstance(el.get(k), list):
                    for c in el[k]:
                        walk(c)
        elif isinstance(el, list):
            for c in el:
                walk(c)

    for e in elements:
        walk(e)
    return {pg: "\n\n".join(parts) for pg, parts in by_page.items()}


ENGINES = {
    "opendataloader": extract_opendataloader,
    "pymupdf": extract_pymupdf,
    "pdfplumber": extract_pdfplumber,
}

ENGINE_META = {
    "opendataloader": ("opendataloader-pdf [로컬 구조화 추출]",
                       "미교정 — 레이아웃 파싱(표/다단). 스캔본은 hybrid OCR 필요. anchor(사건·조문번호) 검증 필수(#34)"),
    "pymupdf": ("PyMuPDF [디지털 텍스트레이어]",
                "미교정 — 텍스트레이어만(스캔 PDF는 빈 텍스트). 표/다단 레이아웃 손실 가능"),
    "pdfplumber": ("pdfplumber [디지털 텍스트레이어]",
                   "미교정 — 텍스트레이어만(스캔 PDF는 빈 텍스트)"),
}


def resolve_engine(preferred: str = "auto") -> tuple[str, list[str]]:
    """엔진 결정 + 경고. 'auto'=opendataloader 우선, 불가 시 pymupdf 폴백."""
    warnings: list[str] = []
    if preferred == "auto":
        if opendataloader_available():
            return "opendataloader", warnings
        if not _has("opendataloader_pdf"):
            warnings.append("opendataloader-pdf 미설치 → pymupdf 폴백 (pip install opendataloader-pdf)")
        elif not java_available():
            warnings.append("Java 11+ 미설치 → opendataloader 사용 불가, pymupdf 폴백 (Adoptium 설치 권장)")
        return "pymupdf", warnings
    if preferred == "opendataloader" and not opendataloader_available():
        reason = "미설치" if not _has("opendataloader_pdf") else "Java 11+ 없음"
        warnings.append(f"opendataloader {reason} → pymupdf 폴백")
        return "pymupdf", warnings
    return preferred, warnings


# ── 파일명 인벤토리 파서 ─────────────────────────────────────

# 민사 전자기록: 법원_사건번호_문서번호_날짜(8자리 또는 YYYY.MM.DD)_문서유형_…_제출자
_CIVIL_E = re.compile(
    r"(?P<court>[^_]+)_(?P<case>\d{4}[가-힣]+\d+)_(?P<docno>\d+)_(?P<date>\d{4}[.\-]?\d{2}[.\-]?\d{2})_(?P<dtype>[^_]+)")


def parse_filename(name: str) -> dict:
    """민사 전자기록 파일명 규칙 해석 (법원_사건번호_문서번호_날짜_문서유형_…). 실패 시 단순명."""
    stem = Path(name).stem
    m = _CIVIL_E.search(stem)
    if m:
        d = m.groupdict()
        return {"문서명": d["dtype"], "사건번호": d["case"], "문서번호": d["docno"],
                "작성일": d["date"], "법원": d["court"], "원본파일": name}
    return {"문서명": stem, "원본파일": name}


# ── 본체 ─────────────────────────────────────────────────────


@dataclass
class ParseResult:
    case_id: str
    extract_dir: str
    inventory: list[dict] = field(default_factory=list)
    chunk_files: list[str] = field(default_factory=list)
    total_pages: int = 0
    engine: str = ""
    scope: str = "full_read"          # 'full_read' | 'index_priority'
    scanned_pdfs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _looks_scanned(pages: list[tuple[int, str]]) -> bool:
    if not pages:
        return False
    avg = sum(len(t) for _, t in pages) / len(pages)
    return avg < 40   # 페이지당 평균 40자 미만 = 스캔본 추정


def parse_record(source: str, out_root: str | None = None, *, engine: str = "auto",
                 chunk_size: int = config.OCR_CHUNK_SIZE, subject: str = "기록") -> ParseResult:
    """사건기록 폴더 또는 단일 PDF → 인벤토리 + 청크 추출본.

    source: 폴더(여러 PDF) 또는 단일 PDF 경로.
    out_root: 산출 루트. 추출본은 (out_root 또는 work_root())/{case_id}/_추출 에 저장된다 —
              단계파일(00~06)이 들어가는 run_dir(=루트/{case_id})과 같은 하위라 사건별로 격리된다.
    """
    src = Path(source)
    pdfs = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
    pdfs = [p for p in pdfs if p.is_file() and p.suffix.lower() == ".pdf"]
    case_id = (src.name if src.is_dir() else src.stem) or "사건"

    # 추출본을 항상 {루트}/{case_id}/_추출 에 둬 단계파일(run_dir=루트/case_id)과 정합 + 사건별 격리
    out_base = (Path(out_root) / case_id) if out_root else (config.work_root() / case_id)
    extract_dir = out_base / "_추출"
    extract_dir.mkdir(parents=True, exist_ok=True)

    eng, warnings = resolve_engine(engine)
    extract = ENGINES[eng]
    label, caveat = ENGINE_META[eng]

    res = ParseResult(case_id=case_id, extract_dir=str(extract_dir), engine=eng, warnings=warnings)

    if not pdfs:
        res.warnings.append(f"PDF 없음: {source}")
        return res

    for pdf in pdfs:
        prefix = pdf.stem
        meta = parse_filename(pdf.name)
        try:
            total = page_count(str(pdf))
        except Exception as e:
            res.warnings.append(f"{pdf.name}: 페이지수 확인 실패({e})")
            continue
        res.total_pages += total
        meta["면수"] = total
        res.inventory.append(meta)

        first_chunk_pages: list[tuple[int, str]] = []
        extracted_any = False
        page = 1
        while page <= total:
            ce = min(page + chunk_size - 1, total)
            out_path = extract_dir / f"{prefix}_p{page:03d}-{ce:03d}.md"
            if out_path.exists() and out_path.stat().st_size > config.RESUME_MIN_BYTES:
                res.chunk_files.append(str(out_path))
                page = ce + 1
                continue
            # 청크별 실제 사용 엔진(폴백 시 라벨/주의문구를 실제 엔진으로 정확히 기록)
            chunk_eng, chunk_label, chunk_caveat = eng, label, caveat
            try:
                pages = extract(str(pdf), page, ce)
            except EngineUnavailable as e:
                res.warnings.append(f"{pdf.name} p.{page}-{ce}: {eng} 실패({e}) → pymupdf 폴백")
                pages = extract_pymupdf(str(pdf), page, ce)
                chunk_eng = "pymupdf"
                chunk_label, chunk_caveat = ENGINE_META["pymupdf"]
            extracted_any = True
            if not first_chunk_pages:
                first_chunk_pages = pages
            front = md.ocr_frontmatter(book=prefix, author="", subject=subject,
                                       start=page, end=ce, source=pdf.name,
                                       engine_label=chunk_label, caveat=chunk_caveat)
            title = f"# {prefix} — p.{page}-{ce} [{chunk_eng} 미교정]\n"
            body = md.assemble_pages(pages)
            out_path.write_text(front + "\n" + title + "\n" + body + "\n", encoding="utf-8")
            res.chunk_files.append(str(out_path))
            page = ce + 1

        if extracted_any and _looks_scanned(first_chunk_pages):
            res.scanned_pdfs.append(pdf.name)
        elif not extracted_any and total:
            # 전 청크가 재개 스킵 → 표본이 없어 스캔 판정 보류(이전 실행에서 이미 경고됐을 것)
            res.warnings.append(f"{pdf.name}: 전 청크 재개 스킵 — 스캔본 판정 생략(이전 산출 확인 권장)")

    # hybrid OCR 가 없으면(=텍스트레이어 부재 스캔본은 빈 텍스트로 남음) 실제 엔진과 무관하게 경고
    if res.scanned_pdfs and not config.odl_hybrid_url():
        res.warnings.append(
            "스캔본 추정: " + ", ".join(res.scanned_pdfs) +
            " — 텍스트레이어 부재. opendataloader hybrid OCR(GIROK_ODL_HYBRID 설정) 또는 별도 OCR 필요.")

    res.scope = "full_read" if res.total_pages <= config.FULL_READ_PAGE_THRESHOLD else "index_priority"
    return res
