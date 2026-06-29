# -*- coding: utf-8 -*-
"""런 디렉터리·단계 산출물 저장. 단계 파일에 자세-스탬프 프론트매터(연구 N4)를 박는다."""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..util import markdown as md


def run_dir(case_id: str, out_root: str | None = None) -> Path:
    base = Path(out_root) if out_root else config.work_root()
    d = base / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_stage(case_dir: str, stage: str, content_md: str, *, case_id: str | None = None,
               brief_type: str | None = None, party_side: str | None = None,
               posture: str | None = None, source_files: list[str] | None = None) -> str:
    """단계 산출물을 STAGE_FILES[stage] 파일명으로 저장(프론트매터 자동 부착)."""
    d = Path(case_dir)
    d.mkdir(parents=True, exist_ok=True)
    fname = config.STAGE_FILES.get(stage, f"{stage}.md")
    fm = md.stage_frontmatter(stage=stage, brief_type=brief_type, party_side=party_side,
                              case_id=case_id or d.name, source_files=source_files, posture=posture)
    body = content_md if content_md.endswith("\n") else content_md + "\n"
    path = d / fname
    path.write_text(fm + "\n" + body, encoding="utf-8")
    return str(path)


def stage_path(case_dir: str, stage: str) -> str:
    return str(Path(case_dir) / config.STAGE_FILES.get(stage, f"{stage}.md"))


def read_stage(case_dir: str, stage: str) -> str:
    p = Path(stage_path(case_dir, stage))
    return p.read_text(encoding="utf-8") if p.exists() else ""
