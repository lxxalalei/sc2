#!/usr/bin/env python3
"""Discover and score potential learning resource sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESOURCE_TERMS = ["资源", "资料", "下载", "课件", "ppt", "pdf", "doc", "练习题", "习题", "试卷", "教案", "讲义", "素材", "电子教材"]
DIRECT_FORMATS = ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "mp3", "wav", "m4a", "mp4", "mov", "zip"]
VIDEO_TERMS = ["视频", "播放", "课程", "网课", "m3u8", "bilibili", "youku", "腾讯视频"]
ARTICLE_TERMS = ["如何", "方法", "经验", "指南", "介绍", "百科", "知识", "科普"]
RISK_TERMS = ["下载器", "高速下载", "破解", "破解版", "成人", "博彩", "贷款", "注册机", "网盘提取码"]
OFFICIAL_HOST_HINTS = ["edu.cn", "gov.cn", "moe.gov.cn", "smartedu.cn", "cbern.com.cn", "eduyun.cn"]

KNOWN_SOURCES = [
    {
        "host_contains": "basic.smartedu.cn",
        "path_contains": "/tchMaterial",
        "known_skill": "smartedu-resources",
        "reason": "国家中小学智慧教育平台站内教材资源入口",
    },
    {
        "host_contains": "basic.smartedu.cn",
        "path_contains": "/syncClassroom",
        "known_skill": "smartedu-resources",
        "reason": "国家中小学智慧教育平台同步课堂入口",
    },
    {
        "host_contains": "basic.smartedu.cn",
        "path_contains": "",
        "known_skill": "smartedu-resources",
        "reason": "国家中小学智慧教育平台通用入口",
    },
]


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def norm(value: Any) -> str:
    return str(value or "").strip()


def text_blob(item: dict[str, Any]) -> str:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    fields = [
        item.get("title"),
        item.get("description"),
        item.get("snippet"),
        item.get("resource_type"),
        item.get("format"),
        item.get("source_name"),
        item.get("source_url") or item.get("url"),
        " ".join(str(x) for x in raw.get("warnings") or []),
    ]
    return " ".join(norm(field) for field in fields if field).lower()


def parse_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme and url.startswith("//"):
        parsed = urllib.parse.urlparse("https:" + url)
    return parsed


def source_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def format_hints(url: str, blob: str) -> list[str]:
    hints: list[str] = []
    suffix_match = re.search(r"\.(pdf|docx?|pptx?|xlsx?|mp3|wav|m4a|mp4|mov|zip|rar|7z)(?:[?#]|$)", url.lower())
    if suffix_match:
        hints.append(suffix_match.group(1))
    for fmt in DIRECT_FORMATS:
        if fmt in blob:
            hints.append(fmt)
    if any(term in blob for term in ["图片", "jpg", "png", "webp"]):
        hints.append("image")
    if any(term in blob for term in ["视频", "m3u8", "mp4"]):
        hints.append("video")
    if any(term in blob for term in ["音频", "mp3", "朗读"]):
        hints.append("audio")
    return list(dict.fromkeys(hints))


def resource_type_hints(blob: str) -> list[str]:
    rules = [
        ("教材", ["教材", "课本", "教科书"]),
        ("习题", ["练习题", "习题", "作业", "可打印"]),
        ("试卷", ["试卷", "测试题"]),
        ("课件", ["课件", "ppt", "pptx"]),
        ("视频", ["视频", "网课", "讲解"]),
        ("音频", ["音频", "朗读", "儿歌"]),
        ("百科文章", ["百科", "科普", "知识"]),
    ]
    hints = [name for name, terms in rules if any(term in blob for term in terms)]
    return list(dict.fromkeys(hints))


def known_source(parsed: urllib.parse.ParseResult) -> dict[str, str] | None:
    host = parsed.netloc.lower()
    path = parsed.path
    for item in KNOWN_SOURCES:
        if item["host_contains"] in host and item["path_contains"] in path:
            return item
    return None


def classify_source(url: str, blob: str, parsed: urllib.parse.ParseResult) -> tuple[str, str]:
    if any(term in blob for term in RISK_TERMS):
        return "download_risk", "reject"
    known = known_source(parsed)
    if known:
        return "known_source", "use_known_source_skill"
    if re.search(r"\.(pdf|docx?|pptx?|xlsx?|mp3|wav|m4a|mp4|mov|zip)(?:[?#]|$)", url.lower()):
        return "resource_page", "extract_direct_candidates"
    if any(term in blob for term in VIDEO_TERMS):
        return "video_page", "profile_site"
    resource_hits = sum(1 for term in RESOURCE_TERMS if term in blob)
    if resource_hits >= 2:
        return "resource_site", "profile_site"
    if resource_hits == 1:
        return "resource_page", "extract_direct_candidates"
    if any(term in blob for term in ARTICLE_TERMS):
        return "article_page", "keep_as_web_candidate"
    return "unknown", "keep_as_web_candidate"


def score_source(source_type: str, next_action: str, blob: str, host: str, hints: list[str]) -> tuple[float, float, float, float, float, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    authority = 8.0 if any(hint in host for hint in OFFICIAL_HOST_HINTS) else 3.0
    if authority >= 8:
        reasons.append("来源域名具备教育或官方属性")

    resource_density = min(sum(1 for term in RESOURCE_TERMS if term in blob) * 2.0 + len(hints) * 1.5, 10.0)
    if resource_density >= 5:
        reasons.append("页面包含较多资源信号")

    accessibility = 7.0
    if any(term in blob for term in ["登录", "会员", "付费", "购买"]):
        accessibility -= 3
        warnings.append("可能需要登录或付费")
    if next_action == "extract_direct_candidates":
        accessibility += 1

    risk_hits = [term for term in RISK_TERMS if term in blob]
    risk = max(10.0 - len(risk_hits) * 4.0, 0.0)
    warnings.extend(f"包含风险词：{term}" for term in risk_hits)

    base = {
        "known_source": 8.0,
        "resource_site": 6.5,
        "resource_page": 6.0,
        "video_page": 5.5,
        "article_page": 3.5,
        "unknown": 2.5,
        "download_risk": 0.0,
    }.get(source_type, 2.0)
    source_score = round(base + authority * 0.25 + resource_density * 0.35 + accessibility * 0.2 + risk * 0.2, 2)
    if source_type == "download_risk":
        source_score = min(source_score, 2.0)
    return (
        min(source_score, 10.0),
        round(authority, 2),
        round(resource_density, 2),
        round(accessibility, 2),
        round(risk, 2),
        list(dict.fromkeys(reasons)),
        list(dict.fromkeys(warnings)),
    )


def normalize_inputs(data: dict[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    query = norm(data.get("query"))
    filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
    if isinstance(data.get("candidates"), list):
        return query, filters, [item for item in data["candidates"] if isinstance(item, dict)]
    raw_results = data.get("search_results")
    if isinstance(raw_results, list):
        items = []
        for result in raw_results:
            if not isinstance(result, dict):
                continue
            url = result.get("url") or result.get("link") or result.get("href") or result.get("source_url")
            if not url:
                continue
            items.append(
                {
                    "source_url": url,
                    "source_name": parse_url(str(url)).netloc,
                    "title": result.get("title") or result.get("name") or "",
                    "description": result.get("snippet") or result.get("description") or result.get("summary") or "",
                    "raw": {"search_result": result},
                }
            )
        return query, filters, items
    raise ValueError("input must contain candidates or search_results")


def discover_one(item: dict[str, Any]) -> dict[str, Any]:
    url = norm(item.get("source_url") or item.get("url"))
    parsed = parse_url(url)
    host = parsed.netloc.lower()
    blob = text_blob(item)
    fmt_hints = format_hints(url, blob)
    type_hints = resource_type_hints(blob)
    source_type, next_action = classify_source(url, blob, parsed)
    score, authority, density, accessibility, risk, reasons, warnings = score_source(source_type, next_action, blob, host, fmt_hints)
    known = known_source(parsed)
    if known:
        reasons.append(known["reason"])
    return {
        "source_id": source_id(url),
        "source_url": url,
        "host": host,
        "title": item.get("title") or "",
        "description": item.get("description") or item.get("snippet") or "",
        "source_type": source_type,
        "source_score": score,
        "authority_score": authority,
        "resource_density_score": density,
        "accessibility_score": accessibility,
        "risk_score": risk,
        "known_skill": known.get("known_skill") if known else "",
        "next_action": next_action,
        "resource_format_hints": fmt_hints,
        "resource_type_hints": type_hints,
        "reasons": list(dict.fromkeys(reasons)),
        "warnings": list(dict.fromkeys(warnings)),
        "raw": {"candidate": item},
    }


def run(args: argparse.Namespace) -> int:
    data = load_json(args.input)
    query, filters, items = normalize_inputs(data)
    discovered = [discover_one(item) for item in items if item.get("source_url") or item.get("url")]
    discovered.sort(key=lambda item: item["source_score"], reverse=True)
    sources = [item for item in discovered if item["next_action"] != "reject" and item["source_score"] >= args.min_score]
    rejected = [item for item in discovered if item["next_action"] == "reject" or item["source_score"] < args.min_score]

    result = {
        "source_discovery_schema": "learning-resource-source-discovery/v1",
        "query": query,
        "filters": filters,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources[: args.limit],
        "rejected_sources": rejected,
        "summary": {
            "input": len(items),
            "sources": min(len(sources), args.limit),
            "rejected": len(rejected),
            "known_sources": sum(1 for item in sources if item["source_type"] == "known_source"),
            "profile_candidates": sum(1 for item in sources if item["next_action"] == "profile_site"),
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover potential learning resource sources")
    parser.add_argument("input", help="Candidate JSON or search results JSON, or '-' for stdin")
    parser.add_argument("--limit", type=int, default=20, help="Maximum accepted sources")
    parser.add_argument("--min-score", type=float, default=3.0, help="Minimum source score")
    parser.add_argument("-o", "--output", help="Write discovery JSON to this file")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
