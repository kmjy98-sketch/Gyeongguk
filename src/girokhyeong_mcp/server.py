# -*- coding: utf-8 -*-
"""Gyeongguk MCP 서버 — 기록형(사건기록→법률서면) 파이프라인 도구·프롬프트.

도구 그룹:
  · 파싱:    parse_record
  · 법령API: law_search · law_detail · precedent_search · precedent_detail · admin_rule_search ·
            verify_case · verify_article · verify_text · get_annexes · verify_annex · cite_check
  · 작성지원: analyze_format · stage_guide · export_docx · save_stage · verify_brief
  · 오케스트레이션: solve_record · server_info
프롬프트: girok_facts · girok_claims · girok_issues · girok_authorities · girok_draft · girok_review
"""
from __future__ import annotations

import shutil

from mcp.server.fastmcp import FastMCP

from . import config, law_api, resources
from .pipeline import (analyze_format as af, export, orchestrator, parse as parse_mod,
                       stages, storage, verify as verify_mod)

mcp = FastMCP("girokhyeong")


# ══ 진단 ═════════════════════════════════════════════════════
@mcp.tool()
def server_info() -> dict:
    """서버 상태·환경 진단: 법령API 키·Java·opendataloader·리소스 배치 여부."""
    return {
        "version": "0.1.0",
        "law_api_key": bool(config.law_api_key()),
        "anthropic_api_key": bool(config.anthropic_api_key()),
        "java": shutil.which("java") is not None,
        "opendataloader": parse_mod.opendataloader_available(),
        "engine_auto_resolves_to": parse_mod.resolve_engine("auto")[0],
        "docx_export": export.available(),
        "missing_resources": resources.missing_resources(),
        "auto_model": config.auto_model(),
        "note": ("opendataloader 는 Java 11+ 필요(Adoptium). 없으면 pymupdf(디지털 텍스트레이어) 폴백. "
                 "스캔 PDF 진짜 OCR 은 opendataloader hybrid(GIROK_ODL_HYBRID) 필요."),
    }


# ══ 파싱 ═════════════════════════════════════════════════════
@mcp.tool()
def parse_record(source: str, out_root: str | None = None, engine: str = "auto",
                 subject: str = "기록") -> dict:
    """사건기록 폴더(또는 단일 PDF)를 추출·인벤토리화. opendataloader 우선, pymupdf 폴백.

    source: 사건기록 폴더 경로 또는 PDF 경로.
    engine: 'auto'|'opendataloader'|'pymupdf'|'pdfplumber'.
    반환: 인벤토리·청크 추출본 경로·총면수·정독모드·스캔본·경고.
    """
    pr = parse_mod.parse_record(source, out_root=out_root, engine=engine, subject=subject)
    return {
        "case_id": pr.case_id, "extract_dir": pr.extract_dir, "engine": pr.engine,
        "total_pages": pr.total_pages, "scope": pr.scope, "inventory": pr.inventory,
        "chunk_files": pr.chunk_files, "scanned_pdfs": pr.scanned_pdfs, "warnings": pr.warnings,
    }


# ══ 법령 API (11) ════════════════════════════════════════════
@mcp.tool()
def law_search(query: str, page: int = 1, page_size: int = 10) -> dict:
    """법령 검색 (법제처 OPEN API). 반환: total, laws[]."""
    return law_api.search_law(query, page, page_size)


@mcp.tool()
def law_detail(law_id: str) -> dict:
    """법령 상세(조문 포함). law_id=법령ID."""
    return law_api.get_law_detail(law_id)


@mcp.tool()
def precedent_search(query: str, page: int = 1, page_size: int = 10) -> dict:
    """판례 검색. 사건번호 직접검색 1순위, 키워드는 단어 수 줄여 재시도. 반환: total, precedents[]."""
    return law_api.search_precedent(query, page, page_size)


@mcp.tool()
def precedent_detail(prec_id: str) -> dict:
    """판례 상세(판시사항·판결요지·참조조문·참조판례·판례내용). prec_id=판례일련번호."""
    return law_api.get_precedent_detail(prec_id)


@mcp.tool()
def admin_rule_search(query: str, page: int = 1, page_size: int = 10) -> dict:
    """행정규칙 검색."""
    return law_api.search_administrative_rule(query, page, page_size)


@mcp.tool()
def verify_case(case_number: str) -> dict:
    """사건번호 존재·요지 검증(정확일치). 본문 직접인용 게이트의 진리값."""
    return law_api.verify_case(case_number)


@mcp.tool()
def verify_article(law_name: str, jo: str | None = None) -> dict:
    """법령(+조문) 존재 검증. jo=조문번호(예 '750')."""
    return law_api.verify_article(law_name, jo)


@mcp.tool()
def verify_text(text: str) -> dict:
    """텍스트에서 사건번호·'법령 제N조'를 추출해 일괄검증. 산출물 종단 검증 훅."""
    return law_api.verify_text(text)


@mcp.tool()
def get_annexes(query: str, search: int = 1, page: int = 1, page_size: int = 20) -> dict:
    """별표·별지서식 목록. search: 1=별표명 2=해당법령 3=별표본문. 본문텍스트 미제공(메타+URL)."""
    return law_api.get_annexes(query, search, page, page_size)


@mcp.tool()
def verify_annex(law_name: str, byeolpyo: str | None = None) -> dict:
    """법령 별표 존재 부분탐지. byeolpyo='별표 1' 등."""
    return law_api.verify_annex(law_name, byeolpyo)


@mcp.tool()
def cite_check(case_number: str, scan_overrule: bool = False, max_following: int = 20) -> dict:
    """판례 인용관계 부분탐지(Shepard's 아님 — 전문검색 위양성 포함). 참조판례+후행인용 후보."""
    return law_api.cite_check(case_number, scan_overrule, max_following)


# ══ 작성 지원 ════════════════════════════════════════════════
@mcp.tool()
def analyze_format(path: str) -> dict:
    """주어진 양식/샘플 서면(docx·pdf·md·txt·hwp)을 역분석해 머리/말미/번호체계/인용형식 구조 추출(req 4)."""
    return af.analyze_format(path)


@mcp.tool()
def stage_guide(stage: str, brief_type: str | None = None, party_side: str | None = None,
                dispute_known: bool = False) -> str:
    """단계별 알고리즘 가이드(사양) 반환. stage ∈ facts|claims|issues|authorities|draft|review."""
    b = stages.STAGE_BUILDERS.get(stage)
    if not b:
        return f"알 수 없는 단계: {stage}. (facts|claims|issues|authorities|draft|review)"
    if stage == "facts":
        return b(party_side, dispute_known)
    if stage == "claims":
        return b(party_side, brief_type)
    if stage == "draft":
        return b(brief_type, party_side, None)
    return b()


@mcp.tool()
def verify_brief(text_or_path: str) -> dict:
    """서면(또는 매트릭스)의 조문·사건번호 실재 일괄검증 + 제출 전 체크리스트 + 게이트(통과/보류/키없음)."""
    return verify_mod.verify_brief(text_or_path)


@mcp.tool()
def save_stage(case_dir: str, stage: str, content_md: str, case_id: str | None = None,
               brief_type: str | None = None, party_side: str | None = None,
               posture: str | None = None) -> dict:
    """단계 산출물을 표준 파일명(00~06)으로 저장(자세-스탬프 프론트매터 부착)."""
    path = storage.save_stage(case_dir, stage, content_md, case_id=case_id,
                              brief_type=brief_type, party_side=party_side, posture=posture)
    return {"saved": path}


@mcp.tool()
def export_docx(in_md: str, out_docx: str, body_pt: int = 11, line_pct: int = 160,
                title: str | None = None) -> dict:
    """마크다운 답안 → docx(바탕 11pt·160%·양쪽맞춤·A4·여백20mm). 최종 HWP/HWPX 는 한글에서 변환."""
    return export.md_to_docx(in_md, out_docx, body_pt=body_pt, line_pct=line_pct, title=title)


# ══ 오케스트레이션 ═══════════════════════════════════════════
@mcp.tool()
def solve_record(source: str, brief_type: str | None = None, party_side: str | None = None,
                 format_sample: str | None = None, engine: str = "auto",
                 out_root: str | None = None, auto: bool = False) -> dict:
    """사건기록 파일/폴더 → 전 단계 진행, 단계별 파일 생성(req 5).

    파싱은 즉시 수행하고 00_인벤토리.md 생성. auto=False(기본)면 단계 플레이북을 반환해
    호스트 LLM이 단계별로 수행(save_stage 저장). auto=True 면 ANTHROPIC_API_KEY 로 서버가
    01~06 파일을 자동 생성.

    brief_type: 소장|민사준비서면_원고|민사준비서면_피고|답변서|형사변론요지서|형사의견서|검토의견서|규제검토의견서 등.
    party_side: '원고 측'|'피고 측'|'검사'|'변호인' — 미정이면 양측 분석·권고 후 확인 요청.
    format_sample: 따라야 할 양식 파일 경로(있으면 역분석해 draft 에 주입).
    """
    return orchestrator.solve_record(
        source, brief_type=brief_type, party_side=party_side, format_sample=format_sample,
        engine=engine, out_root=out_root, auto=auto)


# ══ 프롬프트 ═════════════════════════════════════════════════
@mcp.prompt(title="기록형: 사실관계 정리")
def girok_facts(party_side: str = "", dispute_known: str = "") -> str:
    """사실관계 정리(타임라인·대비표·증거·불일치·사실관계도) 가이드."""
    return stages.facts_guide(party_side or None, bool(dispute_known))


@mcp.prompt(title="기록형: 청구추출")
def girok_claims(party_side: str = "", brief_type: str = "") -> str:
    """청구추출 + 요건 매치업 매트릭스 + 갭 목록 가이드(청구 비명시 시 도출)."""
    return stages.claims_guide(party_side or None, brief_type or None)


@mcp.prompt(title="기록형: 쟁점·법리")
def girok_issues() -> str:
    """쟁점 도출 + 포섭격자(요건×사실×증명책임+셀상태) 가이드."""
    return stages.issues_guide()


@mcp.prompt(title="기록형: 조문·판례")
def girok_authorities() -> str:
    """조문·판례 검색·검증(law_api 도구 사용) 가이드."""
    return stages.authorities_guide()


@mcp.prompt(title="기록형: 서면 작성")
def girok_draft(brief_type: str = "", party_side: str = "") -> str:
    """서면 작성 가이드(서면유형별 골격 + 채점배점 + 형식)."""
    return stages.draft_guide(brief_type or None, party_side or None, None)


@mcp.prompt(title="기록형: 제출 전 검토")
def girok_review() -> str:
    """제출 전 2층 검토(정확성 게이트 + 논리·포섭 5축) 가이드."""
    return stages.review_guide()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
