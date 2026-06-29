# -*- coding: utf-8 -*-
"""auto 모드 — 서버 내부에서 LLM(Anthropic API)이 각 단계를 자동 수행(req 5 완전 자동).

ANTHROPIC_API_KEY 필요. 모델 기본값 claude-opus-4-8(config.auto_model()).
법령·판례 진위는 작성 후 verify_brief(결정적)로 게이트하고 04_조문판례에 검증결과를 남긴다.
host 모드(Claude Code 등에서 도구를 직접 호출)가 진위검증·도구접근 면에서 더 강하다 — auto 는
헤드리스/일괄용 편의 경로다.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from . import stages, storage, verify as verify_mod

_MAX_RECORD_CHARS = 120_000   # 추출본 컨텍스트 상한(초과 시 앞부분 우선)


def _load_record_text(extract_dir: str) -> str:
    parts = []
    total = 0
    for p in sorted(Path(extract_dir).glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        parts.append(t)
        total += len(t)
        if total > _MAX_RECORD_CHARS:
            parts.append("\n\n[…이하 추출본 생략 — 분량 상한. 표적 정독 필요…]")
            break
    return "\n\n".join(parts)


def _call(client, model: str, system: str, user: str, max_tokens: int = 8000) -> str:
    msg = client.messages.create(
        model=model, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def run_auto(*, case_dir: str, pr, brief_type, party_side, format_analysis) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=config.anthropic_api_key())
    model = config.auto_model()

    record = _load_record_text(pr.extract_dir)
    out: dict[str, str] = {}

    def save(stage, content, **kw):
        path = storage.save_stage(case_dir, stage, content, case_id=pr.case_id,
                                  brief_type=brief_type, party_side=party_side, **kw)
        out[stage] = path
        return path

    # 1. 사실관계
    facts = _call(client, model, stages.facts_guide(party_side),
                  f"[사건기록 추출본]\n{record}\n\n위 기록으로 사실관계 정리(A~F)를 마크다운으로만 출력하라.")
    save("facts", facts)

    # 2. 청구추출
    claims = _call(client, model, stages.claims_guide(party_side, brief_type),
                   f"[사실관계]\n{facts}\n\n위 사실관계로 청구추출 + 요건 매치업 매트릭스 + 갭 목록을 출력하라.")
    save("claims", claims)

    # 3. 쟁점·법리
    issues = _call(client, model, stages.issues_guide(),
                   f"[청구추출]\n{claims}\n\n위로 쟁점 도출 + 포섭격자 + 갭리스트를 출력하라.")
    save("issues", issues)

    # 4. 조문·판례 (auto: 모델이 후보 제시 → 작성 후 verify_brief 로 게이트)
    auth = _call(client, model, stages.authorities_guide(),
                 f"[쟁점·법리]\n{issues}\n\n각 쟁점의 적용 조문·관련 판례 후보를 정리표로 출력하라. "
                 f"확신 없는 사건번호는 [검증필요]로 표기(지어내지 말 것).")
    save("authorities", auth)

    # 5. 작성
    draft = _call(client, model, stages.draft_guide(brief_type, party_side, format_analysis),
                  f"[사실관계]\n{facts}\n\n[쟁점·법리]\n{issues}\n\n[조문·판례]\n{auth}\n\n"
                  f"위로 {brief_type or '서면'}을 작성하라(서면 본문 마크다운만).", max_tokens=12000)
    save("draft", draft)

    # 정확성 게이트(결정적) → authorities 에 검증결과 부기
    vb = verify_mod.verify_brief(storage.stage_path(case_dir, "draft"))
    auth2 = auth + f"\n\n---\n### law_api 일괄검증 결과\n- {vb.get('summary')}\n- gate: {vb.get('gate')}\n" + \
        ("- 미검증: " + ", ".join(vb.get("unverified", [])) if vb.get("unverified") else "- 미검증: 없음")
    save("authorities", auth2)

    # 6. 검토
    review = _call(client, model, stages.review_guide(),
                   f"[서면 초안]\n{draft}\n\n위 서면을 논리·포섭 5축으로 적대검토하고 verdict 를 내라.")
    save("review", review)

    return out


def _client_model():
    import anthropic
    return anthropic.Anthropic(api_key=config.anthropic_api_key()), config.auto_model()


def run_auto_case(*, case_dir: str, case_id: str, problem: str, party_side) -> dict:
    """사례형: 사실관계→청구추출→포섭격자→IRAC 답안→검토."""
    client, model = _client_model()
    out: dict[str, str] = {}

    def save(stage, content):
        out[stage] = storage.save_stage(case_dir, stage, content, case_id=case_id, party_side=party_side)

    facts = _call(client, model, stages.facts_guide(party_side),
                  f"[사례 문제]\n{problem}\n\n사실관계 정리(A~F)를 출력하라.")
    save("facts", facts)
    claims = _call(client, model, stages.claims_guide(party_side, None),
                   f"[사실관계]\n{facts}\n\n청구추출 + 요건 매치업 매트릭스 + 갭 목록을 출력하라.")
    save("claims", claims)
    sub = _call(client, model, stages.subsumption_guide(),
                f"[청구추출]\n{claims}\n\n포섭격자(요건×사실 충족여부) + 포섭 결론을 출력하라.")
    save("subsumption", sub)
    answer = _call(client, model, stages.case_answer_guide(party_side),
                   f"[사실관계]\n{facts}\n\n[포섭]\n{sub}\n\n위로 사례형 IRAC 답안을 작성하라.", max_tokens=12000)
    save("case_answer", answer)
    review = _call(client, model, stages.review_guide(),
                   f"[답안]\n{answer}\n\n논리·포섭 5축으로 적대검토하고 verdict 를 내라.")
    save("review", review)
    return out


def run_auto_consult(*, case_dir: str, case_id: str, question: str) -> dict:
    """일반 상담: IRAC 상담의견(면책 포함)."""
    client, model = _client_model()
    ans = _call(client, model, stages.consult_guide(),
                f"[질문]\n{question}\n\n위 질문에 IRAC 상담의견을 작성하라(면책 고지 포함). "
                f"확신 없는 사건번호는 [검증필요]로 표기.", max_tokens=8000)
    path = storage.save_stage(case_dir, "consult", ans, case_id=case_id)
    return {"consult": path}
