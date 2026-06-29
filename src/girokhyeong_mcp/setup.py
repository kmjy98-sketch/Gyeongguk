# -*- coding: utf-8 -*-
"""온보딩 — API 키 발급 안내 · .env 생성 · 라이브 키 검증.

사용:
    python -m girokhyeong_mcp.setup            # 상태 점검 + 다음 할 일 안내(doctor)
    python -m girokhyeong_mcp.setup --init     # .env 생성(.env.example 복사)
    python -m girokhyeong_mcp.setup --check    # LAW_API_KEY 라이브 검증(법령 1건 조회)
    python -m girokhyeong_mcp.setup --init --check
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import config

ISSUE_GUIDE = """\
─────────────────────────────────────────────────────────────
 LAW_API_KEY (법제처 국가법령정보 OPEN API) 발급 방법
─────────────────────────────────────────────────────────────
 1. https://open.law.go.kr  접속 → 회원가입/로그인
 2. 상단 [OPEN API] → [OPEN API 활용신청] (또는 마이페이지 > OPEN API)
 3. 활용 신청(이메일 인증). 신청 시 등록한 이메일의 '@' 앞부분(아이디)이
    그대로 OC 값 = LAW_API_KEY 다.
      예) 이메일이  hong@gmail.com  이면  LAW_API_KEY=hong
 4. .env 파일에 적는다:   LAW_API_KEY=hong
 5. 검증:   python -m girokhyeong_mcp.setup --check
 (승인까지 수 분~수 시간 걸릴 수 있다. 즉시 안 되면 잠시 후 재시도.)
─────────────────────────────────────────────────────────────
"""


def cmd_init() -> None:
    example = config.REPO_ROOT / ".env.example"
    target = Path.cwd() / ".env"
    if target.exists():
        print(f"[init] 이미 존재: {target} (덮어쓰지 않음)")
        return
    if example.exists():
        shutil.copyfile(example, target)
        print(f"[init] 생성: {target}  ← .env.example 복사. LAW_API_KEY 값을 채워라.")
    else:
        target.write_text("LAW_API_KEY=\nANTHROPIC_API_KEY=\n", encoding="utf-8")
        print(f"[init] 생성: {target}  (LAW_API_KEY 값을 채워라)")


def cmd_check() -> bool:
    """라이브 검증: 키로 법령 1건 조회 + 사건번호 검증."""
    from . import law_api
    key = config.law_api_key()
    if not key:
        print("[check] LAW_API_KEY 없음 — .env 또는 환경변수에 설정 후 재시도.")
        print(ISSUE_GUIDE)
        return False
    print(f"[check] LAW_API_KEY 감지(OC='{key}'). 라이브 조회 시도…")
    r = law_api.search_law("민법", page_size=1)
    if "error" in r:
        print(f"[check] 실패: {r['error']}")
        print("        → 키 오타·미승인·네트워크 확인. 승인 직후면 잠시 후 재시도.")
        return False
    total = r.get("total", 0)
    laws = r.get("laws", [])
    name = laws[0].get("법령명") if laws else "(목록 비어있음)"
    print(f"[check] OK — 법령검색 응답: total={total}, 첫 결과='{name}'")
    vc = law_api.verify_case("2003다26051")
    print(f"[check] 판례 검증 샘플(2003다26051): verified={vc.get('verified')}")
    print("[check] 키 정상. 이제 서버를 시작하거나 MCP 클라이언트에 등록하면 된다.")
    return True


def doctor() -> None:
    from .pipeline import parse as P
    from .pipeline import export
    from . import resources
    key = config.law_api_key()
    print("Gyeongguk MCP — 상태 점검\n" + "=" * 50)
    print(f"  LAW_API_KEY            : {'설정됨' if key else '없음 (필수)'}")
    print(f"  ANTHROPIC_API_KEY      : {'설정됨' if config.anthropic_api_key() else '없음 (auto 모드에만 필요)'}")
    print(f"  Java (opendataloader용): {'있음' if P.java_available() else '없음 (디지털 PDF는 pymupdf 폴백)'}")
    print(f"  opendataloader-pdf     : {'사용가능' if P.opendataloader_available() else '미사용 → 폴백 ' + P.resolve_engine('auto')[0]}")
    print(f"  python-docx (export)   : {'있음' if export.available() else '없음 (export_docx 비활성)'}")
    miss = resources.missing_resources()
    print(f"  리소스                 : {'완비' if not miss else '누락 ' + str(miss)}")
    print("=" * 50)
    if not key:
        print("\n다음 할 일: LAW_API_KEY 발급 → .env 작성 → --check\n")
        print(ISSUE_GUIDE)
    else:
        print("\n키가 있다. 라이브 검증: python -m girokhyeong_mcp.setup --check")
    print("\nMCP 클라이언트(예: Claude Code) 등록 예시:")
    print('  { "mcpServers": { "girokhyeong": {')
    print('      "command": "girokhyeong-mcp",')
    print('      "env": { "LAW_API_KEY": "<OC값>" } } } }')


def _force_utf8_stdout() -> None:
    """Windows 한글(cp949) 콘솔에서 em-dash·박스문자 출력 시 UnicodeEncodeError 방지."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    argv = list(sys.argv[1:] if argv is None else argv)
    did = False
    if "--init" in argv:
        cmd_init()
        did = True
    ok = True
    if "--check" in argv:
        ok = cmd_check()
        did = True
    if not did:
        doctor()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
