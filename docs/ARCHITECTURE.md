# 아키텍처

## 설계 원칙

1. **결정적 코어 + LLM 판단 분리.** 진위 검증·OCR·파일 입출력·docx 변환·페이지 추적 같은 결정적 작업은 코드가 한다. 사실관계 해석·청구 도출·법리 포섭·서면 작성·논증 검토 같은 판단은 LLM(호스트 또는 auto 모드의 내부 LLM)이 한다. 서버는 각 판단 단계에 **알고리즘 가이드(사양) + 데이터(요건 카탈로그·서면 템플릿)**를 제공한다.

2. **자체완결(법학볼트 비의존).** `law_api.py`는 표준 라이브러리만 쓰고 외부 워크스페이스 경로에 의존하지 않는다. 키는 환경변수(`LAW_API_KEY`). 어떤 머신에서도 `pip install -e .`로 동작.

3. **단일 정본으로 드리프트 차단.** 룰·요건·서면골격·검토축이 원래 볼트의 여러 파일에 중복·분산돼 드리프트를 일으켰다. 여기서는 `resources/`의 4개 파일에 통합한다.

## 모듈

| 모듈 | 책임 |
|---|---|
| `server.py` | FastMCP 서버. 도구·프롬프트 등록. |
| `law_api.py` | 법제처 OPEN API 클라이언트(11함수). 검색 5 + 검증 6. |
| `pipeline/parse.py` | OCR/추출. 엔진 어댑터(opendataloader/pymupdf/pdfplumber) 레지스트리 + 폴백. 출력 계약: 프론트매터 + `<!-- p.N -->` 페이지마커 + `{prefix}_p{NNN}-{MMM}.md`. |
| `pipeline/stages.py` | 단계별 알고리즘 가이드 생성(facts·claims·issues·authorities·draft·review). 핵심 알고리즘 내장 + 리소스 주입. |
| `pipeline/orchestrator.py` | `solve_record` — 파싱 즉시 수행 + 플레이북 반환(host) 또는 auto 실행. |
| `pipeline/auto_runner.py` | auto 모드(Anthropic API)로 전 단계 자동 수행. |
| `pipeline/verify.py` | `verify_brief` — 조문·사건번호 일괄검증 + 제출 전 체크리스트 + 게이트. |
| `pipeline/analyze_format.py` | 양식 역분석(req 4). |
| `pipeline/export.py` | md → docx. |
| `pipeline/storage.py` | 런 디렉터리·단계 파일 저장(자세-스탬프 프론트매터). |
| `resources.py` | 룰·카탈로그·템플릿·5축 로더. |

## 엔진 어댑터 계약

```
extract(pdf_path, start, end) -> list[(page_no:int(1-based 절대), text:str)]
```

새 엔진은 이 시그니처를 구현하고 `ENGINES`/`ENGINE_META`에 등록하면 끝. `resolve_engine("auto")`는 opendataloader(Java 필요) 우선, 불가 시 pymupdf로 폴백하며 경고를 남긴다.

## 단계 데이터 흐름

```
parse_record ──► 00_인벤토리 + _추출/*.md
   │
facts ──► 01_사실관계 ──► claims ──► 02_청구추출 ──► issues ──► 03_쟁점법리
                                                              │
                              authorities(law_api) ──► 04_조문판례
                                                              │
                                         draft ──► 05_답안 ──► review ──► 06_검토
```

각 단계는 직전 단계 산출(파일)을 입력으로 받는다(R6 순환인용 금지 — 출처는 항상 원 기록·원 판결문, 중간 산출물 재인용 금지).

## host 모드 vs auto 모드

- **host(기본)**: `solve_record`가 플레이북(단계별 guide+input+save_as)을 반환. 호스트 LLM이 MCP 도구(`precedent_search`·`verify_case` 등)를 직접 호출하며 단계를 수행 → 진위검증·도구접근이 강하다. 추가 키 불요. **권장 경로.**
- **auto**: `ANTHROPIC_API_KEY`로 서버가 내부 LLM을 돌려 01~06을 직접 생성. 헤드리스/일괄용. 법령 진위는 작성 후 `verify_brief`로 사후 게이트.

## 게이트(제출 허용)

두 축을 AND 결합:
1. **정확성**(코드, `verify_brief`): unverified 조문·사건번호 없음.
2. **논증**(LLM, 5축): `verdict ∈ {논증가능}`. `논증붕괴`=차단, `보강필요`=must_fix 후 재검토.
