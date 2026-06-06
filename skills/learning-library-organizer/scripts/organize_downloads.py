#!/usr/bin/env python3
"""Organize downloaded learning resources into the final library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


BLOCKED_LIBRARY_SUFFIXES = {".json", ".log", ".tmp", ".manifest"}
FORMAT_ALIASES = {
    "jpeg": "jpg",
    "jpg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
    "pdf": "pdf",
    "doc": "doc",
    "docx": "docx",
    "ppt": "ppt",
    "pptx": "pptx",
    "xls": "xls",
    "xlsx": "xlsx",
    "mp3": "mp3",
    "wav": "wav",
    "m4a": "m4a",
    "mp4": "mp4",
    "mov": "mov",
    "avi": "avi",
    "zip": "zip",
    "html": "html",
}


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_part(value: Any, fallback: str, limit: int = 80) -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text or fallback)[:limit]


def first_value(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple, set)):
            text = str(value).strip()
            if text:
                return text
    return ""


def nested(raw: dict[str, Any], *keys: str) -> Any:
    current: Any = raw
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_format(item: dict[str, Any], path: Path) -> str:
    fmt = first_value(item.get("format"), nested(item, "candidate", "format")).lower().lstrip(".")
    if not fmt:
        fmt = path.suffix.lower().lstrip(".")
    return FORMAT_ALIASES.get(fmt, fmt or "unknown")


def infer_domain(title: str) -> str:
    hints = [
        ("数学", ["数学", "计算", "四则", "口算", "应用题", "几何"]),
        ("语文", ["语文", "拼音", "识字", "阅读", "作文", "唐诗", "宋词", "古诗"]),
        ("英语", ["英语", "单词", "phonics", "自然拼读"]),
        ("科学", ["科学", "百科", "实验", "恐龙", "宇宙", "动物", "植物"]),
        ("音乐", ["儿歌", "音乐", "朗读", "童谣"]),
        ("艺术", ["美术", "绘画", "手工", "艺术"]),
    ]
    lowered = title.lower()
    for domain, keywords in hints:
        if any(keyword.lower() in lowered for keyword in keywords):
            return domain
    return ""


def classify(item: dict[str, Any]) -> tuple[dict[str, str], float, bool]:
    candidate = item.get("candidate") or {}
    raw = candidate.get("raw") or {}
    title = first_value(item.get("title"), candidate.get("title"), Path(str(item.get("local_file") or "")).stem)
    resource_type = first_value(item.get("resource_type"), candidate.get("resource_type"), "资料")

    stage_or_age = first_value(
        candidate.get("stage"),
        candidate.get("stage_or_age"),
        candidate.get("learner_age") and f"{candidate.get('learner_age')}岁",
        raw.get("stage"),
        raw.get("学段"),
        "未分学段",
    )
    grade_or_phase = first_value(candidate.get("grade"), raw.get("grade"), raw.get("年级"), "未分年级")
    domain_or_subject = first_value(
        candidate.get("learning_domain"),
        candidate.get("subject"),
        raw.get("subject"),
        raw.get("学科"),
        infer_domain(title),
        "综合",
    )
    topic_or_type = first_value(candidate.get("core_topic"), candidate.get("topic"), raw.get("topic"), resource_type, "未分主题")
    source_or_version = first_value(
        candidate.get("version"),
        raw.get("version"),
        raw.get("版本"),
        candidate.get("source_name"),
        item.get("source_name"),
        candidate.get("provider"),
        candidate.get("source"),
        "未分来源",
    )

    classification = {
        "stage_or_age": safe_part(stage_or_age, "未分学段"),
        "grade_or_phase": safe_part(grade_or_phase, "未分年级"),
        "domain_or_subject": safe_part(domain_or_subject, "综合"),
        "topic_or_type": safe_part(topic_or_type, "未分主题"),
        "source_or_version": safe_part(source_or_version, "未分来源"),
    }

    score = 0.0
    score += 0.18 if title else 0
    score += 0.16 if classification["stage_or_age"] != "未分学段" else 0
    score += 0.12 if classification["grade_or_phase"] != "未分年级" else 0
    score += 0.16 if classification["domain_or_subject"] != "综合" else 0
    score += 0.14 if classification["topic_or_type"] != "未分主题" else 0
    score += 0.10 if classification["source_or_version"] != "未分来源" else 0
    score += 0.08 if resource_type and resource_type != "资料" else 0
    score += 0.06 if item.get("sha256") else 0

    metadata_confidence = candidate.get("metadata_confidence")
    if isinstance(metadata_confidence, (int, float)):
        score = max(score, min(float(metadata_confidence), 1.0))

    needs_review = score < 0.55
    return classification, round(score, 3), needs_review


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法生成不冲突的文件名: {path}")


def destination_for(item: dict[str, Any], source_path: Path, library_dir: Path, review_threshold: float) -> tuple[Path, dict[str, str], float, bool, str]:
    classification, confidence, needs_review = classify(item)
    fmt = normalize_format(item, source_path)
    title = first_value(item.get("title"), nested(item, "candidate", "title"), source_path.stem)
    digest = first_value(item.get("sha256")) or sha256_file(source_path)
    suffix = source_path.suffix.lower()
    suffix_format = FORMAT_ALIASES.get(suffix.lstrip("."), suffix.lstrip("."))
    if not suffix or suffix in BLOCKED_LIBRARY_SUFFIXES or suffix_format not in FORMAT_ALIASES:
        suffix = f".{fmt}"
    filename = f"{safe_part(title, '未知标题', 70)}_{digest[:8]}{suffix}"

    if confidence < review_threshold or needs_review:
        target_dir = library_dir / "待确认" / safe_part(fmt, "unknown", 30)
        needs_review = True
    else:
        target_dir = (
            library_dir
            / classification["stage_or_age"]
            / classification["grade_or_phase"]
            / classification["domain_or_subject"]
            / classification["topic_or_type"]
            / classification["source_or_version"]
        )
    return unique_destination(target_dir / filename), classification, confidence, needs_review, fmt


def ensure_final_file_allowed(path: Path) -> None:
    if path.suffix.lower() in BLOCKED_LIBRARY_SUFFIXES:
        raise ValueError(f"禁止写入资料库的文件类型: {path.suffix}")


def organize_item(item: dict[str, Any], library_dir: Path, mode: str, dry_run: bool, review_threshold: float) -> dict[str, Any]:
    local_file = item.get("local_file")
    if not local_file:
        raise ValueError("缺少 local_file")
    source_path = Path(str(local_file))
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"文件不存在: {source_path}")

    dest, classification, confidence, needs_review, fmt = destination_for(item, source_path, library_dir, review_threshold)
    ensure_final_file_allowed(dest)

    digest = first_value(item.get("sha256")) or sha256_file(source_path)
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if mode == "move":
            shutil.move(str(source_path), str(dest))
        else:
            shutil.copy2(source_path, dest)

    return {
        "option_id": item.get("option_id"),
        "title": item.get("title"),
        "source_url": item.get("source_url"),
        "original_file": str(source_path),
        "library_file": str(dest),
        "format": fmt,
        "resource_type": first_value(item.get("resource_type"), nested(item, "candidate", "resource_type"), "资料"),
        "classification": classification,
        "classification_confidence": confidence,
        "needs_review": needs_review,
        "sha256": digest,
    }


def run(args: argparse.Namespace) -> int:
    data = load_json(args.input)
    downloaded_files = data.get("downloaded_files") or []
    if not isinstance(downloaded_files, list):
        print("error: downloaded_files must be a list", file=sys.stderr)
        return 2

    library_dir = Path(args.library_dir)
    organized: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for item in downloaded_files:
        if not isinstance(item, dict):
            failures.append({"option_id": None, "title": None, "local_file": None, "error": "下载项不是对象"})
            continue
        try:
            organized.append(organize_item(item, library_dir, args.mode, args.dry_run, args.review_threshold))
        except Exception as exc:
            failures.append(
                {
                    "option_id": item.get("option_id"),
                    "title": item.get("title"),
                    "local_file": item.get("local_file"),
                    "error": str(exc),
                }
            )

    if organized and not failures:
        status = "completed"
    elif organized:
        status = "partial"
    else:
        status = "failed"

    result = {
        "organize_schema": "learning-library-organize/v1",
        "status": status,
        "library_dir": str(library_dir),
        "dry_run": args.dry_run,
        "mode": args.mode,
        "organized_files": organized,
        "failures": failures,
        "summary": {
            "input_files": len(downloaded_files),
            "organized": len(organized),
            "failed": len(failures),
            "needs_review": sum(1 for item in organized if item.get("needs_review")),
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if organized else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize downloaded learning resources into final library")
    parser.add_argument("input", help="Download JSON file, or '-' for stdin")
    parser.add_argument("--library-dir", default="学习资料库", help="Final resource library directory")
    parser.add_argument("--work-dir", default=".learning-resource-work", help="Reserved work directory for callers")
    parser.add_argument("--mode", choices=["copy", "move"], default="copy", help="Copy or move files into the library")
    parser.add_argument("--review-threshold", type=float, default=0.55, help="Classification confidence threshold")
    parser.add_argument("--dry-run", action="store_true", help="Preview organization without writing files")
    parser.add_argument("-o", "--output", help="Write organize JSON to this file outside the final library")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
