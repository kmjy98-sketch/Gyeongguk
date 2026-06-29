# -*- coding: utf-8 -*-
"""오케스트레이터 — solve_record: 사건기록 파일/폴더를 받아 전 단계를 진행하고 단계별 파일 생성(req 5).

두 가지 실행 모드:
  - **host 모드(기본)**: 결정적 단계(파싱)는 즉시 수행하고, 나머지(사실관계·청구추출·법리·작성·검토)는
    각 단계 가이드와 입력을 담은 '플레이북'을 반환한다. 호스트 LLM(Claude Code 등)이 단계별로
    수행하고 save_stage 로 저장한다. 추가 API 키 불요.
  - **auto 모드**: ANTHROPIC_API_KEY 가 있으면 서버 내부에서 LLM이 각 단계를 자동 수행하고
    01~06 파일을 직접 생성한다(완전 자동). 법령·판례 진위는 작성 후 verify_brief(결정적)로 게이트.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from . import parse as parse_mod
from . import stages
from . import storage
from . import verify as verify_mod
from . import analyze_format as af_mod


# ── 인벤토리 마크다운 ────────────────────────────────────────

def _inventory_md(pr: parse_mod.ParseResult) -> str:
    rows = ["| 순번 | 문서명 | 사건번호 | 작성일 | 면수 | 원본파일 |",
            "|---|---|---|---|---|---|"]
    for i, it in enumerate(pr.inventory, 1):
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            i, it.get("문서명", ""), it.get("사건번호", "—"),
            it.get("작성일", "—"), it.get("면수", "—"), it.get("원본파일", "")))
    warn = "\n".join(f"- ⚠ {w}" for w in pr.warnings) or "- (없음)"
    scanned = ", ".join(pr.scanned_pdfs) or "(없음)"
    return (f"## 기록 인벤토리 — {pr.case_id}\n\n"
            f"- 추출 엔진: **{pr.engine}** · 총 {pr.total_pages}면 · "
            f"정독 모드: **{pr.scope}** (≤{config.FULL_READ_PAGE_THRESHOLD}면=전수)\n"
            f"- 스캔본 추정: {scanned}\n"
            f"- 추출본 위치: `{pr.extract_dir}`\n\n"
            + "\n".join(rows) + "\n\n### 경고/주의\n" + warn + "\n")


# ── 플레이북(host 모드) ──────────────────────────────────────

def _playbook(case_dir: str, pr: parse_mod.ParseResult, brief_type, party_side, fa):
    dispute_known = False
    steps = [
        {"stage": "facts", "guide": stages.facts_guide(party_side, dispute_known),
         "input": pr.extract_dir, "save_as": config.STAGE_FILES["facts"]},
        {"stage": "claims", "guide": stages.claims_guide(party_side, brief_type),
         "input": storage.stage_path(case_dir, "facts"), "save_as": config.STAGE_FILES["claims"]},
        {"stage": "issues", "guide": stages.issues_guide(),
         "input": storage.stage_path(case_dir, "claims"), "save_as": config.STAGE_FILES["issues"]},
        {"stage": "authorities", "guide": stages.authorities_guide(),
         "input": storage.stage_path(case_dir, "issues"),
         "tools": ["precedent_search", "verify_case", "verify_article", "verify_brief"],
         "save_as": config.STAGE_FILES["authorities"]},
        {"stage": "draft", "guide": stages.draft_guide(brief_type, party_side, fa),
         "input": [storage.stage_path(case_dir, s) for s in ("facts", "issues", "authorities")],
         "save_as": config.STAGE_FILES["draft"]},
        {"stage": "review", "guide": stages.review_guide(),
         "input": storage.stage_path(case_dir, "draft"),
         "tools": ["verify_brief"], "save_as": config.STAGE_FILES["review"]},
    ]
    return steps


def solve_record(source: str, *, brief_type: str | None = None, party_side: str | None = None,
                 format_sample: str | None = None, engine: str = "auto",
                 out_root: str | None = None, auto: bool = False) -> dict:
    """파싱 → (사실관계·청구추출·법리·검색·작성·검토) 단계 진행."""
    pr = parse_mod.parse_record(source, out_root=out_root, engine=engine)
    case_dir = str(storage.run_dir(pr.case_id, out_root))

    # 00 인벤토리 저장
    inv_path = storage.save_stage(case_dir, "inventory", _inventory_md(pr),
                                  case_id=pr.case_id, brief_type=brief_type, party_side=party_side,
                                  source_files=[Path(f).name for f in pr.chunk_files])

    fa = af_mod.analyze_format(format_sample) if format_sample else None

    common = {
        "case_id": pr.case_id, "case_dir": case_dir, "engine": pr.engine,
        "total_pages": pr.total_pages, "scope": pr.scope, "warnings": pr.warnings,
        "scanned_pdfs": pr.scanned_pdfs, "inventory_file": inv_path,
        "extract_dir": pr.extract_dir, "format_analysis": fa,
    }

    if auto:
        ak = config.anthropic_api_key()
        if not ak:
            common["auto"] = False
            common["note"] = "auto 모드 요청됐으나 ANTHROPIC_API_KEY 없음 → host 플레이북 반환."
            common["playbook"] = _playbook(case_dir, pr, brief_type, party_side, fa)
            return common
        from .auto_runner import run_auto
        results = run_auto(case_dir=case_dir, pr=pr, brief_type=brief_type,
                           party_side=party_side, format_analysis=fa)
        common["auto"] = True
        common["stage_files"] = results
        common["verify"] = verify_mod.verify_brief(storage.stage_path(case_dir, "draft"))
        return common

    common["auto"] = False
    common["playbook"] = _playbook(case_dir, pr, brief_type, party_side, fa)
    common["지침"] = ("플레이북의 각 step 을 순서대로 수행하라: step.guide 를 따라 step.input 을 읽어 "
                     "산출물을 만들고 save_stage(stage=step.stage, ...)로 저장. authorities·review step 은 "
                     "step.tools(precedent_search·verify_case·verify_brief 등)를 호출해 진위를 코드로 검증한다.")
    return common


# ── 사례 풀이 (text/file 문제 → IRAC 답안) ───────────────────

def _resolve_problem(problem: str, case_id: str | None, out_root: str | None) -> tuple[str, str]:
    """problem 이 파일경로면 읽기(pdf 는 추출), 아니면 텍스트로 취급. (본문, case_id) 반환."""
    p = Path(problem)
    try:
        is_file = p.is_file()
    except OSError:
        is_file = False
    if is_file:
        if p.suffix.lower() == ".pdf":
            pr = parse_mod.parse_record(str(p), out_root=out_root)
            chunks = [Path(f).read_text(encoding="utf-8", errors="replace") for f in pr.chunk_files]
            return "\n\n".join(chunks), (case_id or pr.case_id)
        return p.read_text(encoding="utf-8", errors="replace"), (case_id or p.stem)
    return problem, (case_id or "사례")


def solve_case(problem: str, *, party_side: str | None = None, out_root: str | None = None,
               case_id: str | None = None, auto: bool = False) -> dict:
    """사례형 문제(텍스트 또는 파일) → 사실관계·청구추출·포섭격자·IRAC 답안·검토."""
    text, case_id = _resolve_problem(problem, case_id, out_root)
    case_dir = str(storage.run_dir(case_id, out_root))
    prob_path = storage.save_stage(case_dir, "case_problem", text, case_id=case_id, party_side=party_side)

    common = {"mode": "case", "case_id": case_id, "case_dir": case_dir, "problem_file": prob_path}

    steps = [
        {"stage": "facts", "guide": stages.facts_guide(party_side, False),
         "input": prob_path, "save_as": config.STAGE_FILES["facts"]},
        {"stage": "claims", "guide": stages.claims_guide(party_side, None),
         "input": storage.stage_path(case_dir, "facts"), "save_as": config.STAGE_FILES["claims"]},
        {"stage": "subsumption", "guide": stages.subsumption_guide(),
         "input": storage.stage_path(case_dir, "claims"),
         "tools": ["list_claims", "subsumption_grid", "verify_article", "verify_case"],
         "save_as": config.STAGE_FILES["subsumption"]},
        {"stage": "case_answer", "guide": stages.case_answer_guide(party_side),
         "input": [storage.stage_path(case_dir, s) for s in ("facts", "subsumption")],
         "save_as": config.STAGE_FILES["case_answer"]},
        {"stage": "review", "guide": stages.review_guide(),
         "input": storage.stage_path(case_dir, "case_answer"),
         "tools": ["verify_brief"], "save_as": config.STAGE_FILES["review"]},
    ]

    if auto and config.anthropic_api_key():
        from .auto_runner import run_auto_case
        common["auto"] = True
        common["stage_files"] = run_auto_case(case_dir=case_dir, case_id=case_id, problem=text,
                                              party_side=party_side)
        common["verify"] = verify_mod.verify_brief(storage.stage_path(case_dir, "case_answer"))
        return common

    common["auto"] = False
    common["playbook"] = steps
    common["지침"] = ("step 순서대로: facts→claims→subsumption(list_claims/subsumption_grid 로 요건 로드 후 "
                     "사실 대입)→case_answer(IRAC)→review. 각 단계 save_stage 로 저장. 조문·판례는 verify_*.")
    return common


# ── 일반 법률 상담 ───────────────────────────────────────────

def consult(question: str, *, facts: str | None = None, out_root: str | None = None,
            case_id: str | None = None, auto: bool = False) -> dict:
    """법률 질문 → 쟁점·법령/판례 검증·IRAC 상담의견(면책 포함)."""
    case_id = case_id or "상담"
    case_dir = str(storage.run_dir(case_id, out_root))
    q_body = question + (f"\n\n[사실관계]\n{facts}" if facts else "")
    q_path = storage.save_stage(case_dir, "question", q_body, case_id=case_id)

    common = {"mode": "consult", "case_id": case_id, "case_dir": case_dir, "question_file": q_path}

    if auto and config.anthropic_api_key():
        from .auto_runner import run_auto_consult
        common["auto"] = True
        common["stage_files"] = run_auto_consult(case_dir=case_dir, case_id=case_id, question=q_body)
        common["verify"] = verify_mod.verify_brief(storage.stage_path(case_dir, "consult"))
        return common

    common["auto"] = False
    common["guide"] = stages.consult_guide()
    common["input"] = q_path
    common["tools"] = ["law_search", "verify_article", "precedent_search", "verify_case", "verify_brief"]
    common["save_as"] = config.STAGE_FILES["consult"]
    common["지침"] = ("consult_guide 를 따라 질문을 분석하고, law_search/verify_article·precedent_search/verify_case 로 "
                     "근거를 검증한 뒤 IRAC 상담의견(+면책 고지)을 작성해 save_stage(stage='consult')로 저장하라.")
    return common
