#!/usr/bin/env python3
"""Rank learning resource candidates with explainable heuristic scores."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_WEIGHTS = {
    "relevance": 30.0,
    "age_fit": 20.0,
    "authority": 15.0,
    "accessibility": 10.0,
    "format_fit": 10.0,
    "safety": 10.0,
    "metadata_quality": 5.0,
}

SUSPICIOUS_TERMS = ["破解", "成人", "博彩", "贷款", "下载器", "高速下载", "注册机", "破解版", "性感"]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def text_blob(candidate: dict[str, Any]) -> str:
    fields = [
        "title",
        "source_name",
        "resource_type",
        "format",
        "stage",
        "grade",
        "subject",
        "learning_domain",
        "topic",
        "version",
        "volume",
        "provider",
    ]
    analysis = (candidate.get("raw") or {}).get("analysis") or {}
    analysis_text = " ".join(
        [
            norm(analysis.get("text_sample")),
            " ".join(norm(item) for item in as_list(analysis.get("keywords"))),
        ]
    )
    return " ".join(norm(candidate.get(field)) for field in fields) + " " + analysis_text


def contains_any(blob: str, values: list[Any]) -> bool:
    return any(norm(value) and norm(value) in blob for value in values)


def score_relevance(intent: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    blob = text_blob(candidate)

    core_topic = norm(intent.get("core_topic"))
    if core_topic and core_topic in blob:
        score += 12
        reasons.append(f"主题与{intent.get('core_topic')}匹配")
    elif core_topic:
        sub_hits = [part for part in re.split(r"[\s、,，/]+", core_topic) if part and part in blob]
        if sub_hits:
            score += 7
            reasons.append("标题或元数据包含部分主题词")

    subject = norm(intent.get("subject") or intent.get("learning_domain"))
    if subject and subject in blob:
        score += 7
        reasons.append(f"领域或学科匹配{intent.get('subject') or intent.get('learning_domain')}")

    resource_types = as_list(intent.get("resource_types"))
    if not resource_types and candidate.get("source") == "smartedu-textbooks":
        resource_types = ["教材"]
    if contains_any(blob, resource_types):
        score += 7
        reasons.append("资源类型符合需求")

    subtopics = as_list(intent.get("subtopics"))
    if subtopics and contains_any(blob, subtopics):
        score += 4
        reasons.append("子主题匹配")

    version = norm(intent.get("version"))
    if version and version in blob:
        score += 3
        reasons.append(f"版本匹配{intent.get('version')}")

    volume = norm(intent.get("volume"))
    if volume and volume in blob:
        score += 2
        reasons.append(f"册次匹配{intent.get('volume')}")

    return min(score, DEFAULT_WEIGHTS["relevance"]), reasons


def score_age_fit(intent: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    score = 8.0
    reasons: list[str] = []
    warnings: list[str] = []
    blob = text_blob(candidate)

    grade = norm(intent.get("grade"))
    stage = norm(intent.get("stage"))
    age = intent.get("learner_age")

    if grade and grade in blob:
        score += 8
        reasons.append(f"年级匹配{intent.get('grade')}")
    elif grade:
        warnings.append("候选资源未明确匹配目标年级")

    if stage and stage in blob:
        score += 4
        reasons.append(f"阶段匹配{intent.get('stage')}")

    if age and not grade and not stage:
        title = norm(candidate.get("title"))
        if str(age) in title or f"{age}岁" in title:
            score += 8
            reasons.append(f"年龄匹配{age}岁")
        else:
            warnings.append("候选资源未明确标注适用年龄")

    return min(score, DEFAULT_WEIGHTS["age_fit"]), reasons, warnings


def score_authority(candidate: dict[str, Any]) -> tuple[float, list[str]]:
    score = 4.0
    reasons: list[str] = []
    source_text = text_blob(candidate)
    if candidate.get("official") is True:
        score += 8
        reasons.append("官方来源")
    if any(term in source_text for term in ["国家", "教育", "出版社", "官方", "智慧教育"]):
        score += 3
        reasons.append("来源具备较高可信度")
    return min(score, DEFAULT_WEIGHTS["authority"]), reasons


def score_accessibility(candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []
    if candidate.get("downloadable") is True:
        score += 6
        reasons.append("资源可下载")
    elif candidate.get("source_url"):
        score += 3
        reasons.append("资源可访问")
    else:
        warnings.append("缺少可访问链接")

    if candidate.get("requires_auth") is True:
        score += 1
        warnings.append("需要登录或授权访问")
    else:
        score += 4
    return min(score, DEFAULT_WEIGHTS["accessibility"]), reasons, warnings


def score_format_fit(intent: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    score = 3.0
    reasons: list[str] = []
    warnings: list[str] = []
    candidate_format = norm(candidate.get("format") or candidate.get("resource_type"))
    preferences = [norm(item) for item in as_list(intent.get("format_preferences"))]
    resource_types = [norm(item) for item in as_list(intent.get("resource_types"))]

    if preferences and any(pref.lower().replace("/", "") in candidate_format.replace("/", "") for pref in preferences):
        score += 5
        reasons.append("文件格式符合偏好")
    elif preferences:
        warnings.append("格式与用户偏好不完全匹配")
    elif candidate_format:
        score += 4
        reasons.append("候选资源格式明确")

    if resource_types and any(item in text_blob(candidate) for item in resource_types):
        score += 2
    return min(score, DEFAULT_WEIGHTS["format_fit"]), reasons, warnings


def score_safety(candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    blob = text_blob(candidate) + " " + norm(candidate.get("source_url"))
    warnings = [f"包含风险词：{term}" for term in SUSPICIOUS_TERMS if term in blob]
    analysis = (candidate.get("raw") or {}).get("analysis") or {}
    warnings.extend(
        str(item)
        for item in as_list(analysis.get("warnings"))
        if item and any(term in str(item) for term in SUSPICIOUS_TERMS)
    )
    warnings = list(dict.fromkeys(warnings))
    score = DEFAULT_WEIGHTS["safety"] - min(len(warnings) * 4, DEFAULT_WEIGHTS["safety"])
    reasons = ["未发现明显儿童内容风险"] if not warnings else []
    return max(score, 0.0), reasons, warnings


def score_metadata(candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    if isinstance(candidate.get("metadata_confidence"), (int, float)):
        score = float(candidate["metadata_confidence"]) * DEFAULT_WEIGHTS["metadata_quality"]
    else:
        fields = ["title", "source_name", "resource_type", "format", "subject", "topic"]
        score = sum(1 for field in fields if candidate.get(field)) / len(fields) * DEFAULT_WEIGHTS["metadata_quality"]
    analysis = (candidate.get("raw") or {}).get("analysis") or {}
    if isinstance(analysis.get("analysis_confidence"), (int, float)):
        score = max(score, float(analysis["analysis_confidence"]) * DEFAULT_WEIGHTS["metadata_quality"])
    warnings = [] if score >= 3 else ["候选资源元数据不完整"]
    reasons = ["元数据较完整"] if score >= 4 else []
    return round(score, 2), reasons, warnings


def quality_level(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "low"
    return "reject"


def recommendation(level: str) -> str:
    return {
        "excellent": "strong_recommend",
        "high": "recommended",
        "medium": "backup",
        "low": "not_preferred",
        "reject": "reject",
    }[level]


def rank_one(intent: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []

    relevance, r = score_relevance(intent, candidate)
    age_fit, r_age, w_age = score_age_fit(intent, candidate)
    authority, r_auth = score_authority(candidate)
    accessibility, r_access, w_access = score_accessibility(candidate)
    format_fit, r_format, w_format = score_format_fit(intent, candidate)
    safety, r_safety, w_safety = score_safety(candidate)
    metadata_quality, r_meta, w_meta = score_metadata(candidate)

    reasons.extend(r + r_age + r_auth + r_access + r_format + r_safety + r_meta)
    warnings.extend(w_age + w_access + w_format + w_safety + w_meta)

    breakdown = {
        "relevance": round(relevance, 2),
        "age_fit": round(age_fit, 2),
        "authority": round(authority, 2),
        "accessibility": round(accessibility, 2),
        "format_fit": round(format_fit, 2),
        "safety": round(safety, 2),
        "metadata_quality": round(metadata_quality, 2),
    }
    final_score = round(sum(breakdown.values()), 2)
    level = quality_level(final_score)
    return {
        "final_score": final_score,
        "quality_level": level,
        "recommendation": recommendation(level),
        "score_breakdown": breakdown,
        "reasons": reasons[:8],
        "warnings": warnings[:8],
        "candidate": candidate,
    }


def extract_payload(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    intent = data.get("intent") or {}
    if not intent and isinstance(data.get("filters"), dict):
        intent = dict(data["filters"])
    if not intent:
        intent = data
    candidates = data.get("candidates") or data.get("ranked_candidates") or []
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    return intent, candidates


def rank_payload(data: dict[str, Any]) -> dict[str, Any]:
    intent, candidates = extract_payload(data)
    ranked = [rank_one(intent, candidate) for candidate in candidates]
    ranked.sort(key=lambda item: item["final_score"], reverse=True)

    visible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    summary = {"excellent": 0, "high": 0, "medium": 0, "low": 0, "reject": 0}

    for item in ranked:
        level = item["quality_level"]
        summary[level] += 1
        if level == "reject":
            rejected.append(item)
        else:
            item["rank"] = len(visible) + 1
            visible.append(item)

    return {
        "ranking_schema": "learning-resource-ranking/v1",
        "total": len(candidates),
        "ranked_candidates": visible,
        "rejected_candidates": rejected,
        "summary": summary,
    }


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank learning resource candidates")
    parser.add_argument("input", help="Input JSON file, or '-' for stdin")
    parser.add_argument("-o", "--output", help="Write ranking JSON to this file")
    args = parser.parse_args()

    try:
        result = rank_payload(load_json(args.input))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
