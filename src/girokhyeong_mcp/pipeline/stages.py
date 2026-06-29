# -*- coding: utf-8 -*-
"""추론 단계 가이드 빌더 — 각 단계의 알고리즘 명세(호스트 LLM이 따르는 사양)를 생성한다.

핵심 알고리즘은 여기 내장(리소스 미배치 시에도 동작). 리소스(요건 카탈로그·서면 템플릿·
5축)가 있으면 주입해 보강한다. 단계 산출은 storage.save_stage 로 STAGE_FILES 에 저장된다.

근거: 독립판 서면작성 프롬프트 v3 + 기록형풀이 룰 R1~R10 + 논리포섭검토 5축 + 연구 A5(N1~N8).
"""
from __future__ import annotations

import json

from .. import resources

# ── 횡단 정책(모든 단계 공통) ────────────────────────────────
CORE_RULES = """\
## 횡단 규칙 (전 단계 절대 준수)
- **R1 기록 한정**: 제공된 기록에 없는 사실을 만들거나 가정하지 않는다. 모든 사실 주장 뒤에 출처를 괄호로 표기한다 — `(사실관계 제N항)`·`[《문서명》 p.X | "발췌"]`. 쪽수 없는 별첨은 `[《별첨N 항목》]` 폴백.
- **R2 미확인 보류**: 기록에서 확인 불가한 단정은 출력하지 않는다 → `[자료 부족—보류]`. 보류 > 잘못된 단정.
- **R4 실재 판례만**: law_api verify-case/verify-article 로 확인된 것만 본문 인용. 미검증은 `[검증필요: 후보 없음]`. 도구 반환 로그 없이 "확인됨" 단정 금지.
- **R6 순환 인용 금지**: 직전 단계의 요약·표를 다음 단계 '출처'로 재인용하지 않는다. 출처는 항상 원 기록·원 판결문.
- **R7 한자→한글**: 甲→갑, 乙→을, 條→조. 본문에 라틴어·독일어·불필요한 한자 금지(한국어 대역).
- **provenance 태그(연구 N3)**: 법적 결론·계산 날짜도 출처 태그를 단다 — `[computed from: …]`·`[model knowledge — verify]`·`[기록]`.
- **신뢰 마커**: `[확인]`(도구 검증) / `[검증필요]` / `[UNCERTAIN: 사유]` / `[GAP — 사실 추가확인]`. silent gap 금지 — 빈칸은 의도적 표시.
"""


def _wrap(stage_title: str, body: str, save_to: str) -> str:
    return (f"# 단계 가이드 — {stage_title}\n\n{CORE_RULES}\n\n{body}\n\n"
            f"---\n**산출 저장**: 완성한 마크다운을 `save_stage(stage='{save_to}', ...)`로 저장하라.\n")


# ── 1. 사실관계 ──────────────────────────────────────────────

def facts_guide(party_side: str | None = None, dispute_known: bool = False) -> str:
    branch = ("\n> ※ '사실관계 다툼 없음'이 명시되면 D(증거분류)·E(진술불일치표)는 생략하고 "
              "B(다툼없는 전제사실)+C(쟁점↔주장 대비표)를 주산출, A(타임라인)는 선택 강등.") if dispute_known else ""
    side = f"\n- 당사자 입장: **{party_side}** 기준으로 법적 의미 등급을 매긴다." if party_side else \
        "\n- 당사자 입장 미정이면 원·피 양측 기준 모두 등급을 매긴다."
    body = f"""\
## 사실관계 정리 (행위 도출 → 법적의미 타임라인)
기록의 사실을 「[날짜]·[행위자]·[행위]·[대상/효과]」 **행위 단위**로 분해한다(출처 항번호 부착, 일자불명은 `[일자불명]`·추정 금지).{side}

산출 6종:
- **A. 타임라인**: `| 일시 | 사실(행위 단위) | 출처 | 다툼 |`. 시간순. 법적 의미 등급 ◎(쟁점결정—요건을 세우거나 깨는 행위)/○(관련)/△(배경)을 당사자 입장 기준으로. ◎ 행위는 핵심행위 산문 1단락(요건 연결 명시). 다툼 있는 행 끝 ★.
- **B. 다툼 없는 사실 목록**: 양측 진술 일치 사실(답안 전제사실부), 인용 발췌+위치.
- **C. 쟁점↔주장 대비표**: **2열표** `| 원고(○○○) | 피고(○○○) |` — 청구→항변→재항변 주고받기, 빈 셀 `—`. (형사면 `| 검사·피해자 측 | 피의자·변호인 측 |`)
- **D. 증거 분류**: ①서증(계약서·진단서·등기·내역서) ②인적 증거(진술조서·증인신문조서·탄원서) ③객관 증거(CCTV·포렌식·의무기록·통화기록). 객관 증거와 진술 일치 여부 메모.
- **E. 진술 불일치표**: `| # | 항목 | 문서A 진술 | 문서B 진술 | 활용(신빙성·반대신문) |`.
- **F. 사실관계도(Mermaid)**: 당사자·객체 노드, 행위 화살표(라벨=날짜·금액·출처), 점선=다툼. ```mermaid graph LR``` 코드블록. 검토·이해용(서면엔 글로 서술).
{branch}

모든 셀에 출처(`《문서명》 p.X` 또는 `(사실관계 제N항)`)를 부착한다. 발췌 없이 요약만 두지 않는다(no silent supplement)."""
    return _wrap("사실관계", body, "facts")


# ── 2. 청구추출 (req 9) ──────────────────────────────────────

def claims_guide(party_side: str | None = None, brief_type: str | None = None) -> str:
    cat = resources.load_claim_catalog()
    cat_block = _format_catalog(cat) if cat else (
        "> ⚠ 요건사실 카탈로그(claim_catalog.json) 미배치 — 청구권/범죄별 성립요건을 LLM 지식으로 "
        "전개하되 각 요건의 조문·판례를 단계4에서 law_api 로 검증하라.")
    undef = ("\n- **당사자 입장 미정**: 양측 각각의 **승소구조 안전망 층수·불리판례 수를 비교**해 "
             "더 유리한 쪽을 권고하고 사용자 확인을 요청하라(확정 전 자동단정 금지).") if not party_side else \
        f"\n- 당사자 입장: **{party_side}**."
    body = f"""\
## 청구추출 + 요건 매치업 매트릭스 (사실관계 → 가능한 청구·항변 도출)
명시적 청구가 없어도(형사기록·자문형) **사실 신호 → 대응 법리(조문) 후보**를 역추출한다.
파일럿 실증: 형사 상해기록에서 상해죄(§257①)·정당방위(§21①)·과잉방위(§21②③)·심신미약(§10②)·자수(§52①)·인과관계 6쟁점을 사실에서 도출.
{undef}

절차:
1. **청구/공소사실 식별**: 어느 청구권·소인·죄목인가? 어느 측? 사실 신호(예: 옷깃잡기 53초→정당방위, 혈중알코올→심신미약, 119신고→자수)에서 후보를 enumerate.
2. **요건 로드**: 각 후보 청구권/범죄의 성립요건을 카탈로그에서 로드(아래). 항변·재항변도 같이.
3. **매치업 매트릭스**: 청구원인·항변마다 요건을 ①②③로 분해해 행 단위 매핑 —
   `| 요건 | 충족 사실(출처+원문 발췌) | 반대·불리 사실 | 충족도 | 상태 |`
   **상태** = 충족 / 일부 / 다툼 / **공백(기록에 사실 없음)** / 불명(자료부족-보류). 충족 사실은 **기록 원문 발췌만**(요약 금지). 없으면 `공백` — 지어내 채우지 않는다.
   셀 메타: `증명책임:: 원고/피고`(법률요건분류설 — 권리근거/장애/소멸/저지).
4. **갭 목록(킬러산출)**: `공백`·`불명` 행만 모아 입장별 의미 1줄 — 우리 요건이면 입증 보완·**예비적 재구성**, 상대 요건이면 **반박 공격점**(다중 안전망).
5. **다중 안전망 층화**: 핵심 청구는 주위적 구성이 무너져도 결론이 유지되도록 층화(주위적→예비적→최후). 각 층 독립 성립.
6. **상대방 예상 청구**: 상대가 주장할 청구원인·항변·재항변을 최소 1개 도출(R9·R14).

가드: 도출·권고는 입장 미정 단계에서만. 확정 후엔 청구취지 임의 추가·변경 금지. 모든 도출 청구에 `[GAP]`/`[검증필요]` 마커, 자동단정 금지.

{cat_block}"""
    return _wrap("청구추출", body, "claims")


def _format_catalog(cat: dict) -> str:
    lines = ["### 요건사실 카탈로그 (성립요건·증명책임·트리거 사실)"]
    for group in cat.get("groups", []):
        lines.append(f"\n**[{group.get('domain','')}]**")
        for c in group.get("claims", []):
            elems = "·".join(c.get("elements", []))
            burden = c.get("burden", "")
            trig = c.get("triggers", "")
            line = f"- **{c.get('name', c.get('key'))}** ({c.get('law','')}): {elems}"
            if burden:
                line += f" / 증명책임: {burden}"
            if trig:
                line += f" / 트리거: {trig}"
            lines.append(line)
    return "\n".join(lines)


# ── 3. 쟁점·법리 + 포섭격자 ──────────────────────────────────

def issues_guide() -> str:
    body = """\
## 쟁점 도출 + 포섭격자 (요건×사실×증명책임 + 셀 상태머신)
1. **쟁점 도출(최대 6)**: 청구추출의 다툼 요건·갭에서 승소에 필요한 쟁점만 취사(기계적 전부 나열 금지, 배점=쟁점포착 30). 각 쟁점에 잠정 조문 부착.
2. **포섭격자**(쟁점별): `| 요건사실 | 원고(청구원인) | 피고(항변) | 재항변 | 사실·증거(출처) | 셀상태 | 증명책임 |`
   - **셀상태** enum: supported(자백/다툼없음) / partial(일부) / disputed(다툼) / gap(입증부족) / needs-discovery(증거조사필요).
   - 포섭 4슬롯(한 셀 내부): [요건 적시] → [이 사건의 경우 + 사실] → [법적 평가] → [소결].
3. **갭리스트**: 입증책임 진 당사자가 입증 못한 요건사실 목록 = 패소위험 지점.
4. **불리쟁점·불리판례**: ①사실관계 차이 ②후행 대법원 판례 순으로 정면 배제 1개 이상 준비(distinguishing).

다음 단계(법령API): 각 쟁점의 잠정 조문·판례를 verify-article/verify-case 로 검증하고, unverified 행은 상태를 `불명`으로 강등."""
    return _wrap("쟁점·법리", body, "issues")


# ── 4. 법령·판례 검색·검증 (도구 기반) ───────────────────────

def authorities_guide() -> str:
    body = """\
## 조문·판례 검색·검증 (law_api 도구 사용 — 진위는 코드가 판정)
검색 순서(판례탐색 전략 §1):
1. **사건번호 직접조회** 1순위 → `precedent_search` / `verify_case`.
2. **키워드 축소검색**: 2단어는 0건 흔함 → 단어 수 줄여 재시도.
3. **동의어·상위개념 확장**(누출↔유출, 추심↔압류).
4. **결과 상단 유관 사건명 훑기** — 더 직접적·최신 판례 발견 잦음.
5. 조문은 `verify_article(법령, --jo N)` 로 원문 확보.

검증 3단(§5): `검증완료`(번호·선고일·판시 1차소스 대조 일치) / `부분검증`(일부만/취지만) / `검증필요`(확인 불가).
- **검증완료만 본문 직접인용 승격**(따옴표=원문 연속 부분문자열만). `검증필요` 후보 사건번호는 본문 노출 금지(쟁점표·메모에만).
- **판시-사건 1:1 귀속**: 한 사건번호에 이질 판시 여러 개 묶지 말 것.
- 산출: `| 쟁점 | 조문(원문 발췌) | 판례(사건번호+판시 발췌) | 출처 | 검증상태 |`.
- 끝으로 `verify_brief(매트릭스)` 로 일괄검증해 unverified 행 강등.
- 외국법/국제법은 law_api 미적용 → EUR-Lex·UN Treaty·각국 공식 DB 1차 원문(검증 2단·날조가드 동일)."""
    return _wrap("조문·판례", body, "authorities")


# ── 5. 작성 (req 4 양식 분석 결합) ───────────────────────────

def draft_guide(brief_type: str | None = None, party_side: str | None = None,
                format_analysis: dict | None = None) -> str:
    tpl = resources.brief_template(brief_type) if brief_type else {}
    tpl_block = _format_template(brief_type, tpl) if tpl else (
        f"> ⚠ '{brief_type or '미지정'}' 서면 템플릿 미배치 또는 미지정 — 아래 일반 골격 사용:\n"
        "> Ⅰ. 사안의 핵심(5~7문장) → Ⅱ. 쟁점별 주장(법리→포섭→소결) → Ⅲ. 상대방 반박 → Ⅳ. 결론.")
    fmt_block = _format_analysis_block(format_analysis)
    body = f"""\
## 서면 작성
**채점 배점(가인 예선)**: 쟁점포착 30 · 법리·판례조사 30 · 상대방논리대응 20 · 완성도 10 · 형식·인용 10.
- **포섭 강제(30)**: 모든 법리에 사실관계 포섭 문장 1개 이상("이 사건의 경우 ~므로"). 연결어(~므로/~인바)로 사실을 규칙에 매핑.
- **1:1 반박(20)**: 상대 최강 논거를 독립 항으로 정면 반박. 불리쟁점은 (가)press/(나)concede·pivot/(다)drop 중 명시 선택 + 이유 1줄.
- **IRAC는 내부 구조로만**: 본문에 '쟁점/법리/포섭/소결' 라벨 노출 금지(변호사 의견서 산문).
- **검증완료 판시만** 따옴표 직접인용. 번호체계 `1. > 가. > 1) > 가) > ①②③`. 두괄식(소절 제목=결론 명제).
- 미해결 마커(`[VERIFY]`/`[CITE NEEDED]`)가 남은 초안은 final 아님. 약한 논증은 솔직히(누르기/양보/포기).

{tpl_block}

{fmt_block}

## 형식 기본값 (지시문 우선)
- 글꼴 바탕 11pt(제목 16pt 굵게 가운데), 본문 양쪽 맞춤, 줄간격 160%, A4 여백 20mm.
- 머리: 사건/원고/피고 표시 후 정형 인사문. 말미: 날짜(가운데)+작성명의(오른쪽). **작성명의·날짜·파일명은 지시문 표기와 글자 단위 일치**. 본문에 학교·학번 등 인적사항 노출 금지.
- 분량: 초안은 제한의 95% 이내(면당 약 1,300~1,500자 근사, 최종 한글 실측). 초과 시 자구 압축 우선, 글자크기 축소는 최후."""
    return _wrap(f"작성({brief_type or '미지정'})", body, "draft")


def _format_template(brief_type: str, tpl: dict) -> str:
    lines = [f"### 서면 골격 — {brief_type}"]
    if tpl.get("_mirrored_from"):
        lines.append(f"> (거울상: {tpl['_mirrored_from']} 골격을 입장 반전해 적용)")
    if tpl.get("head"):
        lines.append(f"- **머리**: {tpl['head']}")
    for i, step in enumerate(tpl.get("body_skeleton", []), 1):
        lines.append(f"  {i}. {step}")
    if tpl.get("tail"):
        lines.append(f"- **말미**: {tpl['tail']}")
    if tpl.get("mandatory"):
        lines.append(f"- **필수**: {'; '.join(tpl['mandatory'])}")
    if tpl.get("common_omissions"):
        lines.append(f"- **흔한 누락(점검)**: {'; '.join(tpl['common_omissions'])}")
    return "\n".join(lines)


def _format_analysis_block(fa: dict | None) -> str:
    if not fa:
        return ("### 양식\n> 제공된 양식 없음 — 내장 템플릿 + 형식 기본값 사용. "
                "(양식 파일이 있으면 `analyze_format` 후 그 구조를 우선 적용)")
    parts = ["### 제공된 양식 역분석 결과 (이 구조를 우선 적용 — req 4)"]
    if fa.get("제목양식"):
        parts.append(f"- 제목양식: {fa['제목양식']}")
    if fa.get("머리정형"):
        parts.append(f"- 머리정형: {fa['머리정형']}")
    if fa.get("말미정형"):
        parts.append(f"- 말미정형: {fa['말미정형']}")
    if fa.get("번호체계"):
        parts.append(f"- 번호체계: {fa['번호체계']}")
    if fa.get("인용_판례형식_샘플"):
        parts.append(f"- 판례 인용형식: {fa['인용_판례형식_샘플']}")
    if fa.get("인용_조문형식_샘플"):
        parts.append(f"- 조문 인용형식: {fa['인용_조문형식_샘플']}")
    return "\n".join(parts)


# ── 6. 검토 ──────────────────────────────────────────────────

def review_guide() -> str:
    axes = resources.load_review_axes()
    axes_block = json.dumps(axes, ensure_ascii=False, indent=2) if axes else _DEFAULT_AXES
    body = f"""\
## 제출 전 2층 검토
### (1) 정확성(진위) — 코드 게이트
`verify_brief(05_답안.md)` 실행 → unverified 조문·사건번호가 걸린 단정을 본문 직접인용에서 강등.

### (2) 논리·포섭 5축 — LLM 의미판단(작성자와 분리된 적대검증)
사실·판례 *진위*가 아니라 **요건→포섭→결론의 논리**만 적대적으로 검토한다. 봐주지 말 것.
- ① 요건-사실 대응 완전성(최우선): 누락된 성립요건? 포섭 없이 단정한 요건? (피고측) 급소 요건 타격?
- ② 삼단논법: 비약·과잉일반화·과소포섭·충분/필요조건 혼동·순환논증·"명백하다"식 건너뜀.
- ③ 반대논거·구별: 상대 최강논거 정면 처리? distinguishing이 사실차이/후행판례 근거? 다중안전망 각 단계 독립 성립?
- ④ 내부 일관성: 모순 평가·주위/예비 충돌·인부와 본문 불일치.
- ⑤ 결론 정합: 청구취지=결론? 각 쟁점 소결이 종합 결론으로 수렴?

출력 스키마:
```json
{axes_block}
```
verdict=`논증붕괴`면 제출 차단. `보강필요`면 must_fix 우선 보강 후 재검토. 치명(요건 누락·논리 비약) 우선."""
    return _wrap("검토", body, "review")


_DEFAULT_AXES = """{
  "axes": [
    {"axis": "①요건대응", "findings": [{"위치": "", "문제": "", "심각도": "치명|중|경"}], "worst": "치명|중|경"},
    {"axis": "②삼단논법", "findings": [], "worst": ""},
    {"axis": "③반대논거", "findings": [], "worst": ""},
    {"axis": "④일관성", "findings": [], "worst": ""},
    {"axis": "⑤결론정합", "findings": [], "worst": ""}
  ],
  "must_fix": [],
  "verdict": "논증가능|보강필요|논증붕괴"
}"""


# ── 포섭 여부 분석 (사례·기록 공용) ──────────────────────────

def subsumption_guide(claim_keys: list[str] | None = None) -> str:
    """포섭 여부 분석 가이드 — 요건×사실 충족 격자. claim_keys 주면 카탈로그 요건을 주입."""
    grid_block = ""
    if claim_keys:
        rg = resources.requirement_grid(claim_keys)
        if rg.get("grid_markdown"):
            grid_block = "\n### 대상 청구의 요건 격자(카탈로그 로드 — 사실을 대입하라)\n" + rg["grid_markdown"]
        if rg.get("missing"):
            grid_block += f"\n\n> ⚠ 미발견 청구 key: {rg['missing']} — `list_claims` 로 정확한 key 확인."
    body = f"""\
## 포섭 여부 분석 (요건 → 사실 대입 → 충족 판단)
1. **청구권/항변/범죄 식별**: 어떤 권리·항변·죄목의 포섭인가. (key 모르면 `list_claims`로 확인 후 `subsumption_grid` 호출)
2. **요건 분해**: 성립요건을 ①②③로 분해(카탈로그 요건 사용).
3. **사실 대입**: 요건마다 충족 사실을 **기록/사실관계 원문 발췌 + 출처**로 대입. 없으면 `공백`(지어내지 않음, R1·R2).
   `| 요건 | 충족 사실(출처+발췌) | 반대·불리 사실 | 충족여부 | 증명책임 |`
   충족여부 enum: **충족 / 일부 / 다툼 / 공백 / 불명**. 증명책임은 법률요건분류설(원고 권리근거 / 피고 장애·소멸·저지).
4. **충족 판단**: 모든 요건 충족 → 청구 성립. 하나라도 공백·불충족(특히 증명책임 진 측) → 불성립/패소위험. **급소 요건**을 명시.
5. **결론**: "요건 ①②③④ 중 ③이 공백이고 그 증명책임이 원고에게 있으므로 청구는 인용되기 어렵다" 식으로 포섭 결론.

조문·판례 근거는 `verify_article`·`verify_case`로 검증된 것만 본문 인용(R4).{grid_block}"""
    return _wrap("포섭 여부", body, "subsumption")


# ── 사례형 답안 (text 문제 → IRAC 에세이) ────────────────────

def case_answer_guide(party_side: str | None = None) -> str:
    """사례형 IRAC 답안 작성 가이드 (법원제출 서면 아님 — 시험답안 산문)."""
    body = """\
## 사례형 답안 작성 (IRAC)
법원 제출 서면이 아니라 **시험 답안**이다. 머리·말미 정형 없이 IRAC 산문으로 쓴다.
- **쟁점(Issue)**: 무엇이 문제인지(어느 요건이 다툼인지) 적시.
- **규범(Rule)**: 적용 조문 + 판례 법리. **검증완료(verify_case/verify_article)만** 직접인용, 미검증은 `[검증필요]`.
- **포섭(Application)**: "사안의 경우 ~므로"로 사실을 요건에 대입(포섭격자 결론을 산문화). **포섭 문장이 답안의 핵심** — 규칙·사실 나열만 하면 감점.
- **결론(Conclusion)**: 물음에 응답(청구 인용/기각, 죄 성립/불성립).
- 청구·항변 구조는 2열표 `| 원고(○○○) | 피고(○○○) |`로 정리(빈 셀 `—`) 후 산문화.
- 복수 쟁점은 각 IRAC 블록으로, 주위적·예비적 순서화. 상대방 반론 1개 이상 예상·반박.
- 한자→한글(甲→갑), 외국어 금지. 추측 문체 금지(R10)."""
    if party_side:
        body += f"\n- 당사자 입장: **{party_side}** 기준으로 유리하게 구성하되 불리 쟁점은 최소 방어."
    return _wrap("사례 답안", body, "case_answer")


# ── 일반 법률 상담 ───────────────────────────────────────────
CONSULT_DISCLAIMER = (
    "본 답변은 공개 법령·판례에 근거한 **일반 정보 제공**이며, 구체적 사건에 대한 변호사의 법률자문을 "
    "대체하지 않습니다. 실제 사건은 사실관계·증거·최신 판례에 따라 결론이 달라질 수 있으므로 변호사 상담을 권합니다.")


def consult_guide() -> str:
    """일반 법률 상담 가이드 — 질문 → 쟁점 → law_api 검증 → IRAC 상담의견 → 면책."""
    body = f"""\
## 일반 법률 상담
입력: 법률 질문(+ 있으면 사실관계). 출력: 근거 있는 상담의견.
1. **질문·쟁점 정리**: 질문에서 법적 쟁점을 1~N개로 정리. 사실 부족 시 추가 확인할 사실을 `[확인 필요]`로 명시(추측 금지).
2. **법령·판례 조사·검증**: 쟁점별로 `law_search`/`verify_article`(조문 원문)·`precedent_search`/`verify_case`(판례)로 근거 확보. 검증완료만 본문 인용, 미검증은 `[검증필요]`(R4). 사건번호 병기.
3. **IRAC 상담의견**: 쟁점 → 적용 법리(조문·판례) → 사안 적용(일반론 + 사실 있으면 포섭) → 결론·실무 조언. 양면(유리/불리) 균형.
4. **리스크·대안**: 불확실성·반대 견해·시효/기한 등 주의점, 다음 단계(증거 확보·내용증명·소송 등) 제시.
5. **면책 고지**(필수, 답변 말미):
   > {CONSULT_DISCLAIMER}

가드: 실명·실제 진행 중 사건의 구체 전략은 일반론으로만 답하고 변호사 상담을 안내. 외국법은 국내 law_api 미적용 — 별도 1차 출처."""
    return _wrap("법률 상담", body, "consult")


# ── 단계 레지스트리 ──────────────────────────────────────────
STAGE_BUILDERS = {
    "facts": facts_guide,
    "claims": claims_guide,
    "issues": issues_guide,
    "authorities": authorities_guide,
    "draft": draft_guide,
    "review": review_guide,
    "subsumption": subsumption_guide,
    "case_answer": case_answer_guide,
    "consult": consult_guide,
}
