#!/usr/bin/env python3
"""Run SmartEdu textbook candidate search -> analysis -> ranking."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=str(cwd), text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run textbook search/analyze/rank flow")
    parser.add_argument("--stage", help="学段，例如 小学")
    parser.add_argument("--grade", help="年级，例如 三年级")
    parser.add_argument("--subject", help="学科，例如 数学")
    parser.add_argument("--version", help="版本，例如 人教版")
    parser.add_argument("--volume", help="册次，例如 上册")
    parser.add_argument("--query", help="额外关键词")
    parser.add_argument("--show", type=int, default=10, help="候选数量")
    parser.add_argument("--work-dir", default=".learning-resource-flow-work", help="工作目录")
    parser.add_argument("--smartedu-work-dir", help="SmartEdu 索引工作目录；本地已有 data/textbooks.json 时可传项目根目录")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    skills_dir = script_path.parents[2]
    package_root = skills_dir.parent
    work_dir = Path(args.work_dir)
    if not work_dir.is_absolute():
        work_dir = package_root / work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    candidates_json = work_dir / "smartedu-candidates.json"
    analyzed_json = work_dir / "smartedu-analyzed.json"
    ranking_json = work_dir / "smartedu-ranking.json"

    fetch_script = skills_dir / "smartedu-textbooks" / "scripts" / "fetch_textbooks.py"
    analyzer_script = skills_dir / "learning-resource-analyzer" / "scripts" / "analyze_candidates.py"
    ranker_script = skills_dir / "learning-resource-ranker" / "scripts" / "rank_candidates.py"
    selector_script = skills_dir / "learning-resource-selector" / "scripts" / "select_candidates.py"

    smartedu_work_dir = Path(args.smartedu_work_dir) if args.smartedu_work_dir else work_dir / "smartedu-work"
    if not smartedu_work_dir.is_absolute():
        smartedu_work_dir = package_root / smartedu_work_dir

    fetch_cmd = [
        sys.executable,
        str(fetch_script),
        "--list-only",
        "--work-dir",
        str(smartedu_work_dir),
        "--show",
        str(args.show),
        "-o",
        str(candidates_json),
    ]
    for flag, value in [
        ("--stage", args.stage),
        ("--grade", args.grade),
        ("--subject", args.subject),
        ("--version", args.version),
        ("--volume", args.volume),
        ("--query", args.query),
    ]:
        if value:
            fetch_cmd.extend([flag, value])

    run_command(fetch_cmd, package_root)
    run_command([sys.executable, str(analyzer_script), str(candidates_json), "-o", str(analyzed_json)], package_root)
    run_command([sys.executable, str(ranker_script), str(analyzed_json), "-o", str(ranking_json)], package_root)
    run_command([sys.executable, str(selector_script), str(ranking_json)], package_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
