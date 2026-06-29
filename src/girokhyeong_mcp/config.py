"""서버 설정·상수·경로. 환경변수만으로 동작하며 외부 워크스페이스(법학볼트 등)에 의존하지 않는다."""
from __future__ import annotations

import os
from pathlib import Path

# ── 패키지 경로 ──────────────────────────────────────────────
PKG_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PKG_DIR / "resources"

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
