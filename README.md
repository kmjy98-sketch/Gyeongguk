# Gyeongguk — 한국 법률 추론 MCP 서버

한국 법률 작업을 위한 [MCP](https://modelcontextprotocol.io) 서버. 세 가지 흐름을 지원한다:

1. **기록형**(사건기록 → 법률서면): PDF 파일을 주면 **파싱 → 사실관계 → 청구추출 → 법리(쟁점·포섭격자) → 법령API 검증 → 작성 → 검토** 파이프라인을 단계별 파일로 진행.
2. **사례형**(사례 문제 → IRAC 답안): 문제 텍스트/파일을 주면 사실관계 → 청구추출 → **포섭격자** → IRAC 답안 → 검토.
3. **일반 법률 상담**(질문 → 상담의견): 질문을 법령·판례로 검증해 IRAC 상담의견(면책 고지 포함).

공통 엔진: 법제처 OPEN API 검증 + 요건사실 카탈로그 + **포섭 여부 격자**(요건×사실×증명책임) + IRAC + 날조 차단.

기존 '기록형풀이' 룰스킬(개인 옵시디언 볼트)을 **독립 MCP 서버**로 이식·확장한 것이다. 학습용 약점분석·카드·SRS는 의도적으로 제외한다(포섭 추론은 포함).

> ⚠ 이 저장소에는 **코드만** 포함된다. 사건기록·교재·산출 서면 등 민감/저작권 자료는 `.gitignore`로 제외된다.

---

## 파이프라인

| 단계 | 도구/프롬프트 | 산출 파일 |
|---|---|---|
| 파싱 (OCR) | `parse_record` — opendataloader-pdf(로컬) + pymupdf 폴백 | `00_인벤토리.md`, `_추출/*.md` |
| 사실관계 | `girok_facts` — 타임라인·다툼없는사실·주장대비표·증거분류·불일치·사실관계도 | `01_사실관계.md` |
| **청구추출** | `girok_claims` — 요건사실 카탈로그 역매칭 → 가능 청구/항변 도출, 매치업 매트릭스·갭 목록 | `02_청구추출.md` |
| 법리 | `girok_issues` — 쟁점 도출 + 포섭격자(요건×사실×증명책임 + 셀상태) | `03_쟁점법리.md` |
| 법령API | `precedent_search`·`verify_case`·`verify_article`·`verify_brief` (법제처 OPEN API) | `04_조문판례.md` |
| 작성 | `girok_draft` — 서면유형별 골격 + 양식 역분석 + 검증완료만 직접인용 | `05_답안.md` |
| 검토 | `girok_review` — 논리·포섭 5축 + 정확성 게이트 | `06_검토.md` |
| **자동 진행** | `solve_record` — 파일 주면 위 전부 순차 진행, 단계별 파일 생성 | 전체 |

## 핵심 특징

- **청구추출**: 명시적 청구가 없는 사건기록(형사·자문형)에서도 **사실 신호 → 가능한 청구/항변/감경사유**를 역추출한다. 요건사실 카탈로그(`resources/claim_catalog.json`)와 매치업 매트릭스(요건×사실×증명책임, 상태=충족/일부/다툼/공백/불명)로 갭을 식별하고, 당사자 입장 미정 시 양측 승소구조를 비교해 권고한다.
- **작성 양식 분석**: `analyze_format`이 사용자가 준 양식/샘플 서면(docx·pdf·md·hwp 미리보기)을 역분석해 머리·말미·번호체계·인용형식을 추출하고, draft가 그 구조를 따른다. 양식 미제공 시 내장 서면 템플릿(`brief_templates.json`)으로 폴백.
- **법령·판례 검증 내장**: 법제처(국가법령정보센터) OPEN API 직접 호출. 검증완료 판례만 본문 직접인용으로 승격하고, 미검증은 `[검증필요]`로 강등(날조 차단).
- **자세-스탬프 영속화**: 각 단계 산출물 프론트매터에 확정한 결정(당사자 입장·다툼없음 전제 등)을 박아 회귀를 막는다.

## 설치

```bash
git clone https://github.com/kmjy98-sketch/Gyeongguk.git
cd Gyeongguk
pip install -e .            # 최소(mcp + PyMuPDF)
pip install -e ".[all]"     # opendataloader·docx·auto 전부
```

**opendataloader-pdf(권장 OCR 엔진)는 Java 11+ 가 PATH에 있어야 한다** — 없으면 [Adoptium](https://adoptium.net/)에서 설치. Java가 없으면 자동으로 PyMuPDF(디지털 텍스트레이어)로 폴백한다. 스캔 PDF의 진짜 OCR은 opendataloader hybrid 모드가 필요하다:

```bash
pip install "opendataloader-pdf[hybrid]"
opendataloader-pdf-hybrid --port 5002 --ocr-lang "ko,en"
# .env: GIROK_ODL_HYBRID=http://localhost:5002  또는 hybrid 백엔드명
```

## 설정 (온보딩)

자세한 단계는 **[`docs/SETUP.md`](docs/SETUP.md)**. 요약:

```bash
python -m girokhyeong_mcp.setup --init     # .env 생성
# .env 에 LAW_API_KEY=<OC값> 입력  (open.law.go.kr OPEN API 신청 → 이메일 아이디가 OC 값)
python -m girokhyeong_mcp.setup --check    # 라이브 검증(법령 1건 실제 조회)
python -m girokhyeong_mcp.setup            # 전체 상태 점검 + 다음 할 일 안내
```

`.env`(cwd 또는 리포 루트)는 서버가 자동으로 읽는다. 환경변수로 직접 줘도 된다(환경변수 우선).

```
LAW_API_KEY=...          # 필수. open.law.go.kr OPEN API 신청 → 이메일 ID가 OC 값
ANTHROPIC_API_KEY=...    # 선택. solve_record auto 모드(서버 내부 자동 진행)에만
```

MCP 클라이언트 등록 후 **`check_setup`** 도구를 호출하면 키가 살아있는지 즉시 확인된다.

MCP 클라이언트(예: Claude Code) 등록:

```json
{
  "mcpServers": {
    "girokhyeong": {
      "command": "girokhyeong-mcp",
      "env": { "LAW_API_KEY": "...", "GIROK_WORK_ROOT": "C:/work/기록형" }
    }
  }
}
```

또는 `python -m girokhyeong_mcp.server`.

## 사용

가장 간단한 흐름 — 사건기록 폴더를 주고 자동 진행:

```
solve_record(source="C:/cases/2025고합123", brief_type="형사변론요지서", party_side="변호인")
```

`solve_record`는 파싱(결정적)을 즉시 수행해 `00_인벤토리.md`를 만들고, 나머지 단계의 **플레이북**을 반환한다. 호스트 LLM(Claude Code)이 각 단계 가이드를 따라 수행하고 `save_stage`로 저장한다. `auto=True` + `ANTHROPIC_API_KEY`면 서버가 01~06 파일을 직접 생성한다.

양식을 따라야 하면:

```
solve_record(source="...", brief_type="형사의견서", format_sample="C:/양식/우수서면.pdf")
```

## 도구 목록

- **파싱**: `parse_record`
- **법령 API(11)**: `law_search` · `law_detail` · `precedent_search` · `precedent_detail` · `admin_rule_search` · `verify_case` · `verify_article` · `verify_text` · `get_annexes` · `verify_annex` · `cite_check`
- **포섭·청구**: `list_claims`(요건 카탈로그 색인) · `subsumption_grid`(요건×사실 포섭격자)
- **작성 지원**: `analyze_format` · `stage_guide` · `verify_brief` · `save_stage` · `export_docx`
- **오케스트레이션**: `solve_record`(기록형) · `solve_case`(사례형) · `consult`(상담) · `server_info` · `check_setup`
- **프롬프트**: `girok_facts` · `girok_claims` · `girok_issues` · `girok_authorities` · `girok_draft` · `girok_review` · `girok_subsume` · `girok_case` · `girok_consult`

사용 예:
```
solve_case(problem="갑은 을에게 1억을 빌려줬으나 변제기 후에도 안 갚는다. 갑의 청구는?", party_side="원고")
consult(question="전세 보증금을 안 돌려주면?")
subsumption_grid(claim_keys=["tort", "unjust_enrichment"])   # 먼저 list_claims 로 key 확인
```

`server_info`로 환경(법령API 키·Java·opendataloader·리소스 배치)을 점검할 수 있다.

## 구조

```
src/girokhyeong_mcp/
  server.py            FastMCP 서버(도구·프롬프트 등록)
  law_api.py           법제처 OPEN API 클라이언트(stdlib만, 자체완결)
  config.py  resources.py
  pipeline/            parse·stages·orchestrator·verify·export·analyze_format·storage·auto_runner
  resources/           rules.md · claim_catalog.json · brief_templates.json · review_axes.json
  util/                hanja(한자→한글) · markdown(프론트매터·페이지마커)
```

자세한 설계는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), 이식 시 반영한 이전 연구 미반영분은 [`docs/UNREFLECTED_RESEARCH.md`](docs/UNREFLECTED_RESEARCH.md) 참조.

## 라이선스

MIT. 법제처 OPEN API·opendataloader-pdf(Apache-2.0)는 각자의 약관을 따른다.
