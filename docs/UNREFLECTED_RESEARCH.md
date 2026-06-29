# 이전 연구 미반영분 검토 (이식 시 반영)

기존 기록형 룰스킬·연구자료를 MCP로 이식하면서, **이전 연구·지시 중 룰/스킬에 미반영(미영속화)되어 있던 것**을 점검하고 이 서버에 반영했다. (원 요청 항목 10.)

## A. 도구 드리프트 (반영: 재배선)

| 미반영분 | 원 상태 | 이 서버 |
|---|---|---|
| `korean-law-mcp` 은퇴(#49) | 룰·스킬·판례탐색 전반이 여전히 `korean-law-mcp`로 검증 명시 | `law_api`(법제처 직접 API)로 전부 재배선. `rules.md`·`stages.py`·`verify.py` 모두 `verify_case`/`verify_article`/`verify_text` 기준 |
| OCR 엔진 혼재 | SKILL=Colab, 참고서면룰=pdfplumber, #13=LlamaParse 로컬 — 3중 드리프트 | opendataloader-pdf 단일 주엔진 + pymupdf 폴백으로 통일(요청 6) |
| `law_api` CLI 봉인 | CLI 람다가 `a[0]`만 받아 페이지네이션·`get-annexes` search 모드·`cite-check` 옵션이 봉인 | MCP 도구는 함수 직접 래핑 → 전체 파라미터 노출(`page`/`search`/`scan_overrule` 등) |
| `cite_check` 버그 | `판례내용` 키를 참조하나 `get_precedent_detail`이 반환 안 함 → overrule_signal 상시 False | `get_precedent_detail`에 `판례내용` 필드 추가(버그 수정) |

## B. 청구추출 로직의 미영속화 (반영: 전용 모듈 + 데이터화)

- **현 상태**: '사실 신호 → 가능한 청구/항변 도출'이 **파일럿(형사기록→6쟁점)으로 실증만** 됐을 뿐 알고리즘으로 코드화되지 않았다. 룰엔 오히려 "청구취지 변경 금지"만 명문. 매 세션 재발명되는 상태였다.
- **반영**: `girok_claims` 단계 + `claim_catalog.json`(요건사실 카탈로그)로 정식화. 사실 신호(triggers) → 요건 로드 → 매치업 매트릭스(요건×사실×증명책임, 상태 5종) → 갭 목록 → 다중 안전망 → 양측 비교 권고. 독립판 프롬프트 3단계의 "요건 매치업 매트릭스 + 갭식별"을 코어로 채택.

## C. claude-for-legal 연구의 8개 보강점(N1~N8) 중 미반영분 (선별 반영)

| 보강점 | 반영 여부 |
|---|---|
| N1 요건×증거 셀 상태머신 + 갭검출(킬러산출) | ✅ `issues`/`claims` 단계의 포섭격자 셀상태(supported/partial/disputed/gap/needs-discovery) |
| N2 관할/학설별 요건분기 선제표 | ◐ 카탈로그의 `triggers`/`burden`으로 부분 반영(학설대립 분기는 향후 확장) |
| N3 항목별 provenance 인라인 태그 | ✅ `CORE_RULES`의 provenance 태그 강제(`[기록]`·`[computed from:]`·`[model knowledge — verify]`) |
| N4 게이트의 기록 영속화(자세-스탬프) | ✅ `stage_frontmatter`의 `확정자세:` 필드 |
| N5 인용 커버리지 + misgrounded(부분지지=분할) | ✅ `rules.md`·`review_guide`에 misgrounded 분할 명시 |
| N6 구두 vs 서면 캘리브레이션 | ✖ 기록형은 서면 전용이라 제외(범위 밖) |
| N7 약한 논증 솔직성 + 양면 제시 | ✅ `draft_guide`의 "약한 논증은 솔직히(누르기/양보/포기)" |
| N8 증인자세-우선 분기 | ✖ 증인신문(deposition)은 기록형 서면작성 범위 밖 |

## D. 서면 템플릿 정본화 (반영)

- **미반영**: 서면종류별 가이드 §2가 "검사 의견서는 우수답안 실물 부재 → 거울상으로 구성"이라 단정했으나, 제17회 우수서면(검사 의견서) **실물이 이미 존재**. 실물 양식(머리/말미 3단블록·소절제목=결론명제·예비 3층)이 가이드 추상 골격에 역수혈되지 않았다.
- **반영**: `brief_templates.json`을 우수서면 실물 기반으로 구축하고 거울상(`mirror_of`)을 데이터로 명시.

## E. 자료보강 권고 (반영)

- "Phase 0에 일괄추출 선행 + 면수 기준 분기(소형 전수/대형 인덱스+우선순위)" 권고를 `parse_record`에 내장(`FULL_READ_PAGE_THRESHOLD=100`, `scope` 반환).

## 의도적 제외 (요청 2)

- 사례형 약점분석·카드·SRS·드릴·진도보드는 **제외**. 이 서버는 사건기록 서면작성 파이프라인만 담는다.
- legal 플러그인(미국 in-house 계약검토)의 내용·인용은 차용 금지(#1·#48). 구조·메커니즘(셀상태·갭·밴드·태그)만 한국화 차용.
