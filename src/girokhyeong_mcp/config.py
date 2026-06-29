"""서버 설정·상수·경로. 환경변수만으로 동작하며 외부 워크스페이스(법학볼트 등)에 의존하지 않는다."""
from __future__ import annotations

import os
from pathlib import Path

# ── 패키지 경로 ──────────────────────────────────────────────
PKG_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PKG_DIR / "resources"
REPO_ROOT = PKG_DIR.parent.parent          # src/girokhyeong_mcp → 리포 루트


def _autoload_dotenv() -> None:
    """`.env` 를 찾아 os.environ 에 주입(이미 설정된 값은 보존 — env 우선).

    표준 라이브러리만 사용(python-dotenv 의존 없음). 탐색 순서:
    현재 작업디렉터리 → 리포 루트 → GIROK_DOTENV(명시 경로). 이 덕분에 사용자는
    `.env` 에 LAW_API_KEY 만 넣으면 바로 서버를 시작할 수 있다.
    """
    candidates = [Path.cwd() / ".env", REPO_ROOT / ".env"]
    explicit = os.environ.get("GIROK_DOTENV", "").strip()
    if explicit:
        candidates.insert(0, Path(explicit))
    seen = set()
    for path in candidates:
        try:
            rp = path.resolve()
        except OSError:
            continue
        if rp in seen or not rp.is_file():
            continue
        seen.add(rp)
        try:                                # 권한거부·파일잠금 등으로 서버 기동이 막히지 않게(편의 기능)
            content = rp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:   # env 가 .env 보다 우선
                os.environ[k] = v


_autoload_dotenv()

# ── 환경변수 ─────────────────────────────────────────────────
LAW_API_KEY_ENV = "LAW_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
AUTO_MODEL_ENV = "GIROK_AUTO_MODEL"
ODL_HYBRID_ENV = "GIROK_ODL_HYBRID"

DEFAULT_AUTO_MODEL = "claude-opus-4-8"


def law_api_key() -> str | None:
    v = os.environ.get(LAW_API_KEY_ENV, "").strip()
    return v or None


def anthropic_api_key() -> str | None:
    v = os.environ.get(ANTHROPIC_API_KEY_ENV, "").strip()
    return v or None


def auto_model() -> str:
    return os.environ.get(AUTO_MODEL_ENV, "").strip() or DEFAULT_AUTO_MODEL


def odl_hybrid_url() -> str | None:
    v = os.environ.get(ODL_HYBRID_ENV, "").strip()
    return v or None


# ── 산출 위치 ────────────────────────────────────────────────
# 기본 작업 루트: 환경변수 GIROK_WORK_ROOT > cwd/runs
def work_root() -> Path:
    v = os.environ.get("GIROK_WORK_ROOT", "").strip()
    return Path(v) if v else (Path.cwd() / "runs")


# ── 파이프라인 상수 ──────────────────────────────────────────
OCR_CHUNK_SIZE = 30          # 청크당 페이지 수 (출력 파일 분할 단위)
FULL_READ_PAGE_THRESHOLD = 100   # 이하=전수 정독, 초과=인덱스+우선순위 (자료보강 §4)
RESUME_MIN_BYTES = 200       # 재개 스킵: 기존 출력 파일이 이 크기 초과면 건너뜀

# 단계별 산출 파일명 (solve_record 가 생성)
STAGE_FILES = {
    "inventory": "00_인벤토리.md",
    "facts": "01_사실관계.md",
    "claims": "02_청구추출.md",
    "issues": "03_쟁점법리.md",
    "authorities": "04_조문판례.md",
    "draft": "05_답안.md",
    "review": "06_검토.md",
}

# 서면 형식 기본값 (독립판 §7 / 가인 §D — 지시문이 있으면 지시문 우선)
FORMAT_DEFAULTS = {
    "font": "바탕",
    "body_pt": 11,
    "title_pt": 16,
    "line_pct": 160,
    "align": "justify",      # 양쪽맞춤
    "paper": "A4",
    "margin_mm": 20,
    "chars_per_page": (1300, 1500),   # 11pt·160% 근사 (최종은 한글 실측)
    "page_cap": None,        # 지시문에서 받음
}
