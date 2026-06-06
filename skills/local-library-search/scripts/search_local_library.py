#!/usr/bin/env python3
"""Search local learning resource index and output standard candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def norm(value: Any) -> str:
    return str(value or "").strip()


def lower(value: Any) -> str:
    return norm(value).lower()


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_task(path: str) -> dict[str, Any]:
    data = load_json(path)
    if isinstance(data, dict) and data.get("execution_tasks"):
        for task in data["execution_tasks"]:
            if task.get("target_skill") == "local-library-search":
                return dict(task)
    if isinstance(data, dict):
        return data
    raise ValueError("task JSON must be an object")


def build_query(task: dict[str, Any]) -> str:
    if task.get("query"):
        return norm(task["query"])
    filters = task.get("filters") or task
    parts: list[str] = []
    for key in ["learner_age", "stage", "grade", "subject", "learning_domain", "core_topic", "topic"]:
        value = filters.get(key)
        if value:
            parts.append(f"{value}岁" if key == "learner_age" and str(value).isdigit() else str(value))
    parts.extend(str(item) for item in as_list(filters.get("resource_types")))
    parts.extend(str(item) for item in as_list(filters.get("format_preferences")))
    return " ".join(dict.fromkeys(part for part in parts if part))


def tokenize(text: str) -> list[str]:
    raw = re.split(r"[\s、,，/|;；:：()（）【】\\[\\]\"'<>]+", text)
    tokens: list[str] = []
    for item in raw:
        item = item.strip()
        if not item:
            continue
        tokens.append(item.lower())
        if len(item) >= 4 and re.search(r"[\u4e00-\u9fff]", item):
            for size in [2, 3, 4]:
                tokens.extend(
                    gram
                    for gram in (item[index : index + size].strip().lower() for index in range(0, max(len(item) - size + 1, 0)))
                    if gram
                )
    return list(dict.fromkeys(token for token in tokens if token))


def classification(resource: dict[str, Any]) -> dict[str, Any]:
    value = resource.get("classification")
    return value if isinstance(value, dict) else {}


def resource_blob(resource: dict[str, Any]) -> str:
    cls = classification(resource)
    fields = [
        resource.get("title"),
        resource.get("format"),
        resource.get("resource_type"),
        resource.get("source_url"),
        resource.get("library_file"),
        cls.get("stage_or_age"),
        cls.get("grade_or_phase"),
        cls.get("domain_or_subject"),
        cls.get("topic_or_type"),
        cls.get("source_or_version"),
    ]
    return " ".join(lower(item) for item in fields if item)


def format_matches(expected: str, actual: str) -> bool:
    expected = expected.lower().replace("/", "")
    actual = actual.lower().replace("/", "")
    aliases = {
        "pdf": ["pdf"],
        "doc": ["doc", "docx"],
        "docx": ["doc", "docx"],
        "docdocx": ["doc", "docx"],
        "ppt": ["ppt", "pptx"],
        "pptx": ["ppt", "pptx"],
        "pptpptx": ["ppt", "pptx"],
        "image": ["image", "jpg", "jpeg", "png", "gif", "webp"],
        "图片": ["image", "jpg", "jpeg", "png", "gif", "webp"],
        "audio": ["audio", "mp3", "wav", "m4a"],
        "音频": ["audio", "mp3", "wav", "m4a"],
        "video": ["video", "mp4", "mov", "avi"],
        "视频": ["video", "mp4", "mov", "avi"],
    }
    candidates = aliases.get(expected, [expected])
    return any(item in actual for item in candidates)


def score_resource(resource: dict[str, Any], query: str, filters: dict[str, Any], file_exists: bool) -> tuple[float, list[str], list[str]]:
    blob = resource_blob(resource)
    cls = classification(resource)
    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0

    query_tokens = tokenize(query)
    query_hits = [token for token in query_tokens if token in blob]
    if query_tokens:
        ratio = len(query_hits) / len(query_tokens)
        score += ratio * 40
        if query_hits:
            reasons.append(f"查询词命中：{', '.join(query_hits[:6])}")

    field_checks = [
        ("stage", cls.get("stage_or_age"), 8, "学段或适龄匹配"),
        ("grade", cls.get("grade_or_phase"), 8, "年级或阶段匹配"),
        ("subject", cls.get("domain_or_subject"), 12, "学科匹配"),
        ("learning_domain", cls.get("domain_or_subject"), 10, "学习领域匹配"),
        ("core_topic", cls.get("topic_or_type"), 16, "主题匹配"),
        ("topic", cls.get("topic_or_type"), 16, "主题匹配"),
    ]
    for key, actual, points, reason in field_checks:
        expected = filters.get(key)
        if expected and lower(expected) in lower(actual):
            score += points
            reasons.append(reason)

    resource_types = [lower(item) for item in as_list(filters.get("resource_types"))]
    actual_type = lower(resource.get("resource_type"))
    if resource_types and any(item in actual_type or item in blob for item in resource_types):
        score += 10
        reasons.append("资源类型匹配")

    format_preferences = [norm(item) for item in as_list(filters.get("format_preferences") or filters.get("expected_formats"))]
    actual_format = lower(resource.get("format"))
    if format_preferences and any(format_matches(item, actual_format) for item in format_preferences):
        score += 8
        reasons.append("格式偏好匹配")
    elif format_preferences:
        warnings.append("格式与偏好不完全匹配")

    semantic_hit = bool(query_hits or reasons)
    if (query_tokens or filters) and not semantic_hit:
        return 0.0, [], warnings

    confidence = resource.get("classification_confidence")
    if isinstance(confidence, (int, float)):
        score += min(float(confidence), 1.0) * 8

    if file_exists:
        score += 6
    else:
        warnings.append("本地文件不存在")

    if resource.get("needs_review"):
        warnings.append("资源分类需要复核")
        score -= 4

    return round(max(score, 0.0), 3), list(dict.fromkeys(reasons)), list(dict.fromkeys(warnings))


def stage_from_classification(cls: dict[str, Any]) -> Any:
    value = cls.get("stage_or_age")
    if value in {"未分学段", "未分适龄"}:
        return None
    return value


def grade_from_classification(cls: dict[str, Any]) -> Any:
    value = cls.get("grade_or_phase")
    if value in {"未分年级", "未分阶段"}:
        return None
    return value


def candidate_from_resource(resource: dict[str, Any], score: float, reasons: list[str], warnings: list[str], rank: int) -> dict[str, Any]:
    cls = classification(resource)
    library_file = norm(resource.get("library_file"))
    source_url = norm(resource.get("source_url"))
    resource_key = norm(resource.get("resource_key")) or hashlib.sha1(library_file.encode("utf-8")).hexdigest()[:16]
    size = None
    if library_file and Path(library_file).exists():
        size = Path(library_file).stat().st_size
    metadata_confidence = min(
        1.0,
        0.35
        + (0.25 if score >= 35 else 0.1 if score > 0 else 0)
        + float(resource.get("classification_confidence") or 0) * 0.35
        + (0.05 if library_file and Path(library_file).exists() else 0),
    )
    return {
        "source": "local-library-search",
        "source_name": "本地学习资料库",
        "source_url": source_url,
        "resource_id": resource_key,
        "title": resource.get("title") or Path(library_file).stem,
        "description": f"本地资料库已归档资源，匹配分 {score}",
        "resource_type": resource.get("resource_type") or "",
        "format": resource.get("format") or "",
        "stage": stage_from_classification(cls),
        "grade": grade_from_classification(cls),
        "subject": cls.get("domain_or_subject") if cls.get("domain_or_subject") != "综合" else None,
        "learning_domain": cls.get("domain_or_subject") if cls.get("domain_or_subject") != "综合" else None,
        "version": cls.get("source_or_version") if cls.get("source_or_version") != "未分来源" else None,
        "volume": None,
        "topic": cls.get("topic_or_type") if cls.get("topic_or_type") != "未分主题" else None,
        "provider": cls.get("source_or_version") or "本地资料库",
        "official": False,
        "downloadable": True,
        "requires_auth": False,
        "size": size,
        "metadata_confidence": round(metadata_confidence, 3),
        "local_file": library_file,
        "raw": {
            "rank": rank,
            "match_score": score,
            "match_reasons": reasons,
            "warnings": warnings,
            "index_resource": resource,
        },
    }


def load_resources(index_file: Path) -> list[dict[str, Any]]:
    if not index_file.exists():
        return []
    data = json.loads(index_file.read_text(encoding="utf-8"))
    resources = data.get("resources")
    if not isinstance(resources, list):
        raise ValueError("resources.json 格式错误：resources 必须是列表")
    return [item for item in resources if isinstance(item, dict)]


def run(args: argparse.Namespace) -> int:
    task = load_task(args.task_json) if args.task_json else {}
    filters = task.get("filters") or {}
    query = args.query or build_query(task)
    if not query and filters:
        query = build_query({"filters": filters})

    resources = load_resources(Path(args.index_file))
    matches: list[tuple[float, dict[str, Any], list[str], list[str]]] = []
    for resource in resources:
        library_file = Path(norm(resource.get("library_file")))
        file_exists = bool(resource.get("library_file")) and library_file.exists() and library_file.is_file()
        if not file_exists and not args.include_missing:
            continue
        score, reasons, warnings = score_resource(resource, query, filters, file_exists)
        if score >= args.min_score:
            matches.append((score, resource, reasons, warnings))

    matches.sort(key=lambda item: item[0], reverse=True)
    candidates = [
        candidate_from_resource(resource, score, reasons, warnings, index + 1)
        for index, (score, resource, reasons, warnings) in enumerate(matches[: args.limit])
    ]
    output = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "local-library-search",
        "query": query,
        "filters": filters,
        "index_file": str(args.index_file),
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
    }
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search local learning resource index")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--task-json", help="Task or intent JSON")
    parser.add_argument("--index-file", default=".learning-resource-work/index/resources.json", help="External resources.json index file")
    parser.add_argument("--limit", type=int, default=10, help="Maximum candidates")
    parser.add_argument("--min-score", type=float, default=8.0, help="Minimum local match score")
    parser.add_argument("--include-missing", action="store_true", help="Include records whose library file is missing")
    parser.add_argument("-o", "--output", help="Write candidates JSON to this file")
    return parser


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
