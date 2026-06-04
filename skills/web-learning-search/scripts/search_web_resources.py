#!/usr/bin/env python3
"""Normalize web search results into standard learning resource candidates."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RISK_TERMS = ["下载器", "高速下载", "破解", "破解版", "成人", "博彩", "贷款", "注册机"]
OFFICIAL_HINTS = ["edu.cn", "gov.cn", "moe.gov.cn", "smartedu.cn", "cbern.com.cn", "人民教育出版社", "出版社"]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def norm(value: Any) -> str:
    return str(value or "").strip()


def load_task(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("execution_tasks"):
        for task in data["execution_tasks"]:
            if task.get("target_skill") == "web-learning-search":
                merged = dict(task)
                merged.setdefault("intent", {k: v for k, v in data.items() if k != "execution_tasks"})
                return merged
    if isinstance(data, dict):
        return data
    raise ValueError("task JSON must be an object")


def build_query(task: dict[str, Any]) -> str:
    if task.get("query"):
        return str(task["query"]).strip()
    filters = task.get("filters") or task
    parts: list[str] = []
    for key in ["learner_age", "stage", "grade", "subject", "learning_domain", "core_topic", "topic"]:
        value = filters.get(key)
        if value:
            parts.append(f"{value}岁" if key == "learner_age" and str(value).isdigit() else str(value))
    parts.extend(str(item) for item in as_list(filters.get("resource_types")))
    parts.extend(str(item) for item in as_list(task.get("expected_formats") or filters.get("format_preferences")))
    if filters.get("printable"):
        parts.append("可打印")
    return " ".join(dict.fromkeys(part for part in parts if part))


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def unwrap_redirect_url(url: str) -> str:
    url = html.unescape(url)
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    for key in ["url", "u", "target"]:
        if key in query and query[key]:
            return query[key][0]
    return url


def parse_search_html(html_text: str, limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.S,
    )
    matches = list(pattern.finditer(html_text))
    for index, match in enumerate(matches[:limit]):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else start + 1200
        block = html_text[start:end]
        snippet_match = re.search(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.S)
        if not snippet_match:
            snippet_match = re.search(r'<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>', block, re.S)
        results.append(
            {
                "url": unwrap_redirect_url(match.group("url")),
                "title": clean_text(match.group("title")),
                "snippet": clean_text(snippet_match.group(1)) if snippet_match else "",
            }
        )
    return results


def load_search_results(path: str) -> list[dict[str, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_results = data.get("search_results") if isinstance(data, dict) else data
    if not isinstance(raw_results, list):
        raise ValueError("search results JSON must be a list or contain search_results list")

    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link") or item.get("href") or item.get("source_url")
        title = item.get("title") or item.get("name")
        snippet = item.get("snippet") or item.get("description") or item.get("summary") or ""
        if url and title:
            results.append({"url": str(url), "title": str(title), "snippet": str(snippet)})
    return results


def infer_format(url: str, text: str) -> str:
    blob = f"{url} {text}".lower()
    suffix_match = re.search(r"\.(pdf|docx?|pptx?|xlsx?|jpe?g|png|gif|webp|mp3|wav|m4a|mp4|mov|avi|zip|rar|7z)(?:[?#]|$)", blob)
    if suffix_match:
        ext = suffix_match.group(1)
        if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
            return "image"
        if ext in {"mp3", "wav", "m4a"}:
            return "audio"
        if ext in {"mp4", "mov", "avi"}:
            return "video"
        return ext
    if any(term in blob for term in ["视频", "video", "bilibili", "youku"]):
        return "video"
    if any(term in blob for term in ["音频", "朗读", "mp3", "audio"]):
        return "audio"
    if any(term in blob for term in ["图片", "image"]):
        return "image"
    return "html"


def infer_resource_type(text: str, fmt: str) -> str:
    blob = text.lower()
    rules = [
        ("习题", ["练习", "习题", "作业", "可打印"]),
        ("试卷", ["试卷", "测试题", "单元测试"]),
        ("课件", ["课件", "ppt", "pptx"]),
        ("视频", ["视频", "网课", "讲解视频"]),
        ("音频", ["音频", "朗读", "儿歌", "mp3"]),
        ("图片", ["图片", "图卡", "卡片"]),
        ("绘本", ["绘本"]),
        ("百科文章", ["百科", "科普", "知识"]),
        ("讲义", ["讲义", "教案", "素材"]),
    ]
    for resource_type, terms in rules:
        if any(term in blob for term in terms):
            return resource_type
    if fmt == "video":
        return "视频"
    if fmt == "audio":
        return "音频"
    if fmt == "image":
        return "图片"
    if fmt in {"ppt", "pptx"}:
        return "课件"
    if fmt in {"pdf", "doc", "docx"}:
        return "文档"
    return "网页"


def infer_subject(text: str) -> tuple[Any, Any]:
    blob = text.lower()
    if any(term in blob for term in ["数学", "四则", "运算", "分数"]):
        return "数学", "数学"
    if any(term in blob for term in ["语文", "拼音", "识字", "唐诗", "宋词", "成语"]):
        return "语文", "文学"
    if any(term in blob for term in ["英语", "英文", "自然拼读"]):
        return "英语", "英语"
    if any(term in blob for term in ["百科", "恐龙", "宇宙", "动物", "人体"]):
        return None, "百科"
    return None, None


def infer_context_field(filters: dict[str, Any], key: str, text: str) -> Any:
    value = filters.get(key)
    if not value:
        return None
    return value if str(value).lower() in text.lower() else None


def infer_topic(filters: dict[str, Any], text: str) -> Any:
    topic = filters.get("core_topic") or filters.get("topic")
    if not topic:
        return None
    topic_text = str(topic)
    blob = text.lower()
    if topic_text.lower() in blob:
        return topic
    parts = [part for part in re.split(r"[\s、,，/]+", topic_text) if part]
    hits = [part for part in parts if part.lower() in blob]
    return topic if len(hits) >= max(1, len(parts) // 2) else None


def metadata_confidence(item: dict[str, Any]) -> float:
    fields = ["title", "source_url", "description", "resource_type", "format"]
    present = sum(1 for field in fields if item.get(field))
    return round(present / len(fields), 2)


def candidate_from_result(result: dict[str, str], rank: int, filters: dict[str, Any]) -> dict[str, Any]:
    url = result["url"]
    title = result["title"]
    snippet = result["snippet"]
    combined = f"{title} {snippet} {url}"
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    fmt = infer_format(url, combined)
    resource_type = infer_resource_type(combined, fmt)
    subject, learning_domain = infer_subject(combined)
    downloadable = fmt not in {"html", "video", "audio"}
    warnings = [f"包含风险词：{term}" for term in RISK_TERMS if term in combined]
    official = any(hint in combined or hint in host for hint in OFFICIAL_HINTS)

    candidate = {
        "source": "web-learning-search",
        "source_name": host or "网页搜索",
        "source_url": url,
        "resource_id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
        "title": title,
        "description": snippet,
        "resource_type": resource_type,
        "format": fmt,
        "stage": infer_context_field(filters, "stage", combined),
        "grade": infer_context_field(filters, "grade", combined),
        "subject": subject,
        "learning_domain": learning_domain,
        "version": filters.get("version"),
        "volume": filters.get("volume"),
        "topic": infer_topic(filters, combined),
        "provider": host,
        "official": official,
        "downloadable": downloadable,
        "requires_auth": any(term in combined for term in ["登录", "会员", "付费", "购买"]),
        "size": None,
        "metadata_confidence": 0.0,
        "raw": {
            "rank": rank,
            "snippet": snippet,
            "host": host,
            "warnings": warnings,
        },
    }
    candidate["metadata_confidence"] = metadata_confidence(candidate)
    return candidate


def run(args: argparse.Namespace) -> int:
    task = load_task(args.task_json) if args.task_json else {}
    filters = task.get("filters") or {}
    query = args.query or build_query(task)
    if not query:
        print("error: --query or --task-json with query/filters is required", file=sys.stderr)
        return 2

    if args.search_results_json:
        results = load_search_results(args.search_results_json)[: args.limit]
    elif args.html_file:
        html_text = Path(args.html_file).read_text(encoding="utf-8")
        results = parse_search_html(html_text, args.limit)
    else:
        print("error: provide --search-results-json from agent search results, or --html-file for local debugging", file=sys.stderr)
        return 2

    candidates = [candidate_from_result(result, index + 1, filters) for index, result in enumerate(results)]
    output = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "web-learning-search",
        "query": query,
        "filters": filters,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
    }
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize web search results into learning resource candidates")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--task-json", help="JSON task or intent file")
    parser.add_argument("--search-results-json", help="Agent search results JSON file")
    parser.add_argument("--html-file", help="Parse a saved search result HTML page for local debugging")
    parser.add_argument("--limit", type=int, default=10, help="Maximum candidates")
    parser.add_argument("-o", "--output", help="Write candidate JSON to this file")
    return parser


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
