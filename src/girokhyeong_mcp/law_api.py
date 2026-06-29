# -*- coding: utf-8 -*-
"""법제처(국가법령정보센터) OPEN API 직접 클라이언트 — 표준라이브러리(urllib)만, 외부 의존 0.

법학볼트 `.agent/lib/law_api.py` 를 독립 이식한 것. 차이점:
  - API 키는 환경변수 LAW_API_KEY 만 사용(워크스페이스 .env 경로 의존 제거 — 이식성).
  - get_precedent_detail 에 '판례내용' 필드 추가(원본의 cite_check 가 참조하나 누락됐던 키 — 버그 수정).
  - korean-law-mcp 참조 제거(해당 MCP 은퇴, law_api 단독).

엔드포인트: lawSearch.do(검색)·lawService.do(상세), OC=key, type=XML.

CLI:  python -m girokhyeong_mcp.law_api verify-case "2003다26051"
      python -m girokhyeong_mcp.law_api verify-article "민법" --jo 750
"""
from __future__ import annotations

import os
import re
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

BASE = "https://www.law.go.kr/DRF"


def _load_key():
    k = os.environ.get("LAW_API_KEY")
    return k.strip() if k else None


def _request(endpoint, params, timeout=25):
    key = _load_key()
    if not key:
        return None, "LAW_API_KEY 없음 (환경변수 LAW_API_KEY 설정 필요 — open.law.go.kr OPEN API)"
    p = {"OC": key, "type": "XML"}
    p.update(params)
    url = "%s/%s?%s" % (BASE, endpoint, urllib.parse.urlencode(p))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read()
        return ET.fromstring(raw), None
    except ET.ParseError as e:
        return None, "XML 파싱 실패: %s" % e
    except Exception as e:  # 네트워크·타임아웃 포함
        return None, "%s: %s" % (type(e).__name__, e)


def _txt(el, tag, default=""):
    return (el.findtext(tag, default) or default).strip()


def _jonum(s):
    """조문번호 정규화: '0750'·'750'→'750' (선행 0 제거, 첫 숫자군)."""
    m = re.match(r"0*(\d+)", s or "")
    return m.group(1) if m else ""


# ── 1차 조회 ─────────────────────────────────────────────────

def search_law(query, page=1, page_size=10):
    root, err = _request("lawSearch.do", {"target": "law", "query": query,
                                          "display": min(page_size, 50), "page": page})
    if err:
        return {"error": err}
    laws = [{"법령ID": _txt(l, "법령ID"), "법령명": _txt(l, "법령명한글"),
             "약칭": _txt(l, "법령약칭명"), "구분": _txt(l, "법령구분명"),
             "소관부처": _txt(l, "소관부처명"), "시행일자": _txt(l, "시행일자"),
             "공포일자": _txt(l, "공포일자")} for l in root.findall(".//law")]
    return {"total": int(_txt(root, ".//totalCnt", "0") or 0), "laws": laws}


def get_law_detail(law_id):
    root, err = _request("lawService.do", {"target": "law", "ID": law_id})
    if err:
        return {"error": err}
    arts = []
    for u in root.findall(".//조문단위"):
        head = _txt(u, "조문내용")
        body = []
        for el in u.iter():
            if el.tag in ("항내용", "호내용", "목내용") and (el.text or "").strip():
                body.append(" ".join((el.text or "").split()))
        arts.append({"조문번호": _txt(u, "조문번호"), "조문여부": _txt(u, "조문여부"),
                     "조문제목": _txt(u, "조문제목"),
                     "조문내용": "\n".join([head] + body) if head else "\n".join(body)})
    return {"법령ID": _txt(root, ".//법령ID"), "법령명": _txt(root, ".//법령명한글"),
            "시행일자": _txt(root, ".//시행일자"), "조문수": len(arts), "조문": arts}


def search_precedent(query, page=1, page_size=10):
    root, err = _request("lawSearch.do", {"target": "prec", "query": query,
                                          "display": min(page_size, 50), "page": page})
    if err:
        return {"error": err}
    ps = [{"판례일련번호": _txt(p, "판례일련번호"), "사건명": _txt(p, "사건명"),
           "사건번호": _txt(p, "사건번호"), "선고일자": _txt(p, "선고일자"),
           "선고": _txt(p, "선고"), "법원명": _txt(p, "법원명"),
           "판시사항": _txt(p, "판시사항")} for p in root.findall(".//prec")]
    return {"total": int(_txt(root, ".//totalCnt", "0") or 0), "precedents": ps}


def get_precedent_detail(prec_id):
    """판례 상세 (ID=판례일련번호). '판례내용'(전문) 포함 — cite_check 변경신호 탐지용."""
    root, err = _request("lawService.do", {"target": "prec", "ID": prec_id})
    if err:
        return {"error": err}
    return {"사건명": _txt(root, ".//사건명"), "사건번호": _txt(root, ".//사건번호"),
            "선고일자": _txt(root, ".//선고일자"), "법원명": _txt(root, ".//법원명"),
            "판시사항": _txt(root, ".//판시사항"), "판결요지": _txt(root, ".//판결요지"),
            "참조조문": _txt(root, ".//참조조문"), "참조판례": _txt(root, ".//참조판례"),
            "판례내용": _txt(root, ".//판례내용")}


def search_administrative_rule(query, page=1, page_size=10):
    root, err = _request("lawSearch.do", {"target": "admrul", "query": query,
                                          "display": min(page_size, 50), "page": page})
    if err:
        return {"error": err}
    rules = [{"행정규칙ID": _txt(r, "행정규칙ID"), "행정규칙명": _txt(r, "행정규칙명"),
              "소관부처": _txt(r, "소관부처명"), "시행일자": _txt(r, "시행일자")}
             for r in root.findall(".//admrul")]
    return {"total": int(_txt(root, ".//totalCnt", "0") or 0), "rules": rules}


# ── 자동검증 ─────────────────────────────────────────────────

def verify_case(case_number):
    """판례 사건번호 존재·요지 검증. 정확일치 시 verified=True + 요지."""
    res = search_precedent(case_number, page_size=20)
    if "error" in res:
        return {"verified": False, "사건번호": case_number, "error": res["error"]}
    tgt = re.sub(r"\s+", "", case_number or "")
    for p in res.get("precedents", []):
        if re.sub(r"\s+", "", p.get("사건번호") or "") == tgt:
            return {"verified": True, "사건번호": p["사건번호"], "사건명": p.get("사건명"),
                    "법원명": p.get("법원명"), "선고일자": p.get("선고일자"),
                    "판시사항": (p.get("판시사항") or "")[:200]}
    return {"verified": False, "사건번호": case_number,
            "note": "검색 %d건 중 사건번호 정확일치 없음" % res.get("total", 0)}


def verify_article(law_name, jo=None):
    """법령(+조문) 존재 검증. jo=조문번호."""
    sres = search_law(law_name)
    if "error" in sres:
        return {"verified": False, "법령명": law_name, "error": sres["error"]}
    match = None
    for l in sres.get("laws", []):
        if l.get("법령명") == law_name or l.get("약칭") == law_name:
            match = l
            break
    if not match and sres.get("laws"):
        match = sres["laws"][0]
    if not match:
        return {"verified": False, "법령명": law_name, "note": "법령 검색결과 없음"}
    out = {"verified": True, "법령명": match["법령명"], "법령ID": match["법령ID"],
           "시행일자": match.get("시행일자")}
    if jo is not None:
        det = get_law_detail(match["법령ID"])
        if "error" in det:
            out["조문검증"] = {"error": det["error"]}
        else:
            want = _jonum(str(jo))
            cands = [a for a in det.get("조문", []) if _jonum(a.get("조문번호")) == want]
            found = next((a for a in cands if a.get("조문여부") == "조문"), None) or (cands[0] if cands else None)
            out["조문검증"] = ({"verified": True, "조문번호": found["조문번호"],
                              "조문제목": found.get("조문제목"),
                              "조문내용": (found.get("조문내용") or "")[:200]}
                             if found else {"verified": False, "조문": "제%s조" % want,
                                            "note": "미발견(법령 조문수 %s)" % det.get("조문수")})
    return out


_CASE_RE = re.compile(r"\d{2,4}[가-힣]{1,3}\d+")
_ART_RE = re.compile(r"([가-힣]{1,9}법)\s*제\s*(\d+)\s*조")


def verify_text(text):
    """산출물 텍스트에서 사건번호·'법령 제N조'를 추출해 일괄검증 (#13·#45-C 종단 검증 훅)."""
    cases = sorted(set(_CASE_RE.findall(text)))
    arts = sorted(set(_ART_RE.findall(text)))  # (법령명, 조문번호)
    out = {"case_results": [], "article_results": [], "unverified": [], "api_error": None}
    for c in cases:
        r = verify_case(c)
        row = {"사건번호": c, "verified": bool(r.get("verified")), "사건명": r.get("사건명")}
        if r.get("error"):                       # 키부재·네트워크 오류는 산출에 보존(인용 가짜와 구별)
            row["error"] = r["error"]
            out["api_error"] = out["api_error"] or r["error"]
        out["case_results"].append(row)
        if not r.get("verified"):
            out["unverified"].append("판례 " + c)
    for (lname, jo) in arts:
        r = verify_article(lname, jo)
        av = r.get("조문검증", {})
        ok = bool(r.get("verified")) and av.get("verified", True)
        row = {"법령": lname, "조": "제%s조" % jo, "verified": ok}
        err = r.get("error") or av.get("error")
        if err:
            row["error"] = err
            out["api_error"] = out["api_error"] or err
        out["article_results"].append(row)
        if not ok:
            out["unverified"].append("%s 제%s조" % (lname, jo))
    out["summary"] = "사건번호 %d / 조문 %d / 미검증 %d" % (
        len(cases), len(arts), len(out["unverified"]))
    return out


# ── 별표·인용검증 ────────────────────────────────────────────

def get_annexes(query, search=1, page=1, page_size=20):
    """별표·별지서식 목록 (target=licbyl). 본문텍스트 미제공 — 메타+다운로드URL만.
    search: 1=별표명 2=해당법령 3=별표본문."""
    root, err = _request("lawSearch.do", {"target": "licbyl", "query": query,
                                          "search": search, "display": min(page_size, 100), "page": page})
    if err:
        return {"error": err}
    DOM = "https://www.law.go.kr"
    items = []
    for b in root.findall(".//licbyl"):
        hwp = _txt(b, "별표서식파일링크")
        pdf = _txt(b, "별표서식PDF파일링크")
        items.append({"별표일련번호": _txt(b, "별표일련번호"), "별표명": _txt(b, "별표명"),
                      "별표번호": _txt(b, "별표번호"), "별표구분": _txt(b, "별표구분"),
                      "법령명": _txt(b, "법령명"), "소관부처": _txt(b, "소관부처명"),
                      "hwp_url": (DOM + hwp) if hwp else "", "pdf_url": (DOM + pdf) if pdf else ""})
    return {"total": int(_txt(root, ".//totalCnt", "0") or 0), "annexes": items}


def verify_annex(law_name, byeolpyo=None):
    """법령 별표 존재 부분탐지. byeolpyo='별표 1' 등 → 별표명 부분매칭."""
    res = get_annexes(law_name, search=2, page_size=50)
    if "error" in res:
        return {"verified": False, "법령명": law_name, "error": res["error"]}
    items = res.get("annexes", [])
    if byeolpyo is None:
        return {"verified": bool(items), "법령명": law_name, "별표수": len(items),
                "별표목록": [a["별표명"] for a in items[:20]]}
    key = re.sub(r"\s+", "", byeolpyo)
    for a in items:
        if key in re.sub(r"\s+", "", a.get("별표명") or ""):
            return {"verified": True, "별표명": a["별표명"], "pdf_url": a["pdf_url"], "hwp_url": a["hwp_url"]}
    return {"verified": False, "법령명": law_name, "별표": byeolpyo,
            "note": "별표 %d건 중 '%s' 미발견" % (len(items), byeolpyo)}


def cite_check(case_number, scan_overrule=False, max_following=20):
    """판례 인용관계 부분탐지 (Shepard's 아님 — 법제처 API 한계).
    참조판례(backward·확실) + 후행인용 후보(forward·전문검색 위양성 포함) + (옵션)변경신호 휴리스틱."""
    base = verify_case(case_number)
    out = {"사건번호": case_number, "exists": bool(base.get("verified")),
           "cited_by_target": [], "citing_target": [],
           "limitations": "전문검색 위양성·별칭변경 누락·변경판단은 본문 휴리스틱(scan_overrule)"}
    if not base.get("verified"):
        out["note"] = "대상 판례 미확인"
        return out
    tgt = re.sub(r"\s+", "", case_number)
    sres = search_precedent(case_number, page_size=20)
    serial = next((p.get("판례일련번호") for p in sres.get("precedents", [])
                   if re.sub(r"\s+", "", p.get("사건번호") or "") == tgt), None)
    if serial:
        ref = (get_precedent_detail(serial).get("참조판례") or "")
        out["cited_by_target"] = sorted(set(_CASE_RE.findall(ref)))
    for p in search_precedent(case_number, page_size=max_following).get("precedents", []):
        if re.sub(r"\s+", "", p.get("사건번호") or "") == tgt:
            continue
        row = {"사건번호": p.get("사건번호"), "사건명": p.get("사건명"), "선고일자": p.get("선고일자")}
        if scan_overrule and p.get("판례일련번호"):
            d2 = get_precedent_detail(p["판례일련번호"])
            row["overrule_signal"] = bool(re.search(r"변경|배치되는 범위|폐기",
                                          (d2.get("판례내용") or "") + (d2.get("판결요지") or "")))
        out["citing_target"].append(row)
    return out


# ── CLI (독립 테스트용) ──────────────────────────────────────

_CLI = {
    "search-law": lambda a: search_law(a[0]),
    "get-annexes": lambda a: get_annexes(a[0]),
    "cite-check": lambda a: cite_check(a[0]),
    "law-detail": lambda a: get_law_detail(a[0]),
    "search-prec": lambda a: search_precedent(a[0]),
    "prec-detail": lambda a: get_precedent_detail(a[0]),
    "search-admrul": lambda a: search_administrative_rule(a[0]),
    "verify-case": lambda a: verify_case(a[0]),
    "verify-article": None,  # _main에서 --jo 처리
    "verify-text": None,     # _main에서 파일/텍스트 처리
    "verify-annex": None,    # _main에서 --byeolpyo 처리
}


def _main(argv):
    if not argv or argv[0] not in _CLI:
        print("usage: law_api.py {%s} <args> [--jo N] [--byeolpyo \"별표 N\"]" % "|".join(_CLI))
        return 2
    cmd, rest = argv[0], argv[1:]
    jo = None
    if "--jo" in rest:
        i = rest.index("--jo")
        jo = rest[i + 1] if i + 1 < len(rest) else None
        rest = rest[:i] + rest[i + 2:]
    if cmd == "verify-article":
        out = verify_article(rest[0], jo)
    elif cmd == "verify-text":
        src = rest[0]
        text = open(src, encoding="utf-8").read() if os.path.isfile(src) else src
        out = verify_text(text)
    elif cmd == "verify-annex":
        bp = None
        if "--byeolpyo" in rest:
            i = rest.index("--byeolpyo")
            bp = rest[i + 1] if i + 1 < len(rest) else None
            rest = rest[:i] + rest[i + 2:]
        out = verify_annex(rest[0], bp)
    else:
        out = _CLI[cmd](rest)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
