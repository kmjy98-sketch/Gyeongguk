# -*- coding: utf-8 -*-
"""네트워크·외부 키 불요 스모크 테스트. `python -m pytest` 또는 `python tests/test_smoke.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_server_imports_and_registers():
    from girokhyeong_mcp import server
    assert server.mcp.name == "girokhyeong"


def test_resources_present_and_load():
    from girokhyeong_mcp import resources as R
    assert R.missing_resources() == [], "리소스 4종 모두 배치돼야 함"
    assert len(R.load_rules()) > 1000
    assert R.load_review_axes().get("axes")
    # 카탈로그·템플릿 조회
    assert R.claim_elements("tort").get("elements")
    bt = R.brief_template("형사의견서")
    assert bt.get("body_skeleton")
    assert bt.get("mirror_of") == "형사변론요지서"


def test_stage_guides_build():
    from girokhyeong_mcp.pipeline import stages
    assert "요건사실 카탈로그" in stages.claims_guide("변호인", "형사변론요지서")
    for st in ("facts", "issues", "authorities", "review"):
        assert stages.STAGE_BUILDERS[st]()  # 인자 없는 빌더
    assert "채점 배점" in stages.draft_guide("민사소장", "원고 측", None)


def test_filename_parser():
    from girokhyeong_mcp.pipeline.parse import parse_filename
    d = parse_filename("서울중앙지방법원_2026가합12345_001001_2026.01.12_소장_(소장)_원고.pdf")
    assert d["사건번호"] == "2026가합12345"
    assert d["문서명"] == "소장"


def test_engine_resolution_has_fallback():
    from girokhyeong_mcp.pipeline import parse as P
    eng, warnings = P.resolve_engine("auto")
    assert eng in ("opendataloader", "pymupdf")


def test_verify_text_extracts_citations():
    from girokhyeong_mcp import law_api
    out = law_api.verify_text("형법 제257조 위반, 대법원 2020도6874 판결 참조")
    # 키 없어도 추출은 됨(검증은 실패할 수 있음)
    assert any("257" in a["조"] for a in out["article_results"])
    assert any("2020도6874" == c["사건번호"] for c in out["case_results"])


def test_verify_brief_gate_distinguishes_no_key():
    import os
    os.environ.pop("LAW_API_KEY", None)
    from girokhyeong_mcp.pipeline import verify as V
    r = V.verify_brief("대법원 2003다26051 판결, 민법 제750조")
    assert r["gate"] == "키없음"   # 키 부재를 '보류'와 구별


def test_subsumption_grid_loads_requirements():
    from girokhyeong_mcp import resources as R
    rg = R.requirement_grid(["tort", "self_defense", "없는키"])
    assert {c["key"] for c in rg["claims"]} == {"tort", "self_defense"}
    assert rg["missing"] == ["없는키"]
    assert "| 요건 |" in rg["grid_markdown"]


def test_case_and_consult_guides_build():
    from girokhyeong_mcp.pipeline import stages
    assert "IRAC" in stages.case_answer_guide("원고 측")
    g = stages.consult_guide()
    assert "면책" in g or "대체하지" in g    # 면책 고지 포함


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print("ALL PASS")
