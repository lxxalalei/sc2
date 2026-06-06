#!/usr/bin/env python3
"""Extract direct learning resource links from simple web source profiles."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


RESOURCE_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "avi",
    "zip",
    "rar",
    "7z",
}
AUTH_TERMS = ["登录", "会员", "付费", "授权", "购买", "token", "accessToken", "Authorization"]
OFFICIAL_HINTS = ["edu.cn", "gov.cn", "moe.gov.cn", "smartedu.cn", "cbern.com.cn", "出版社"]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "a" and data.get("href"):
            self.current_link = {"url": data["href"], "text": ""}
            self.links.append(self.current_link)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() == "a":
            self.current_link = None

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if self.current_link is not None:
            self.current_link["text"] = clean_text(f"{self.current_link.get('text', '')} {text}")


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def absolute_url(base_url: str, url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(url))


def extension_for_url(url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    return "jpg" if suffix == "jpeg" else suffix


def normalized_format(ext: str) -> str:
    if ext == "jpeg":
        return "jpg"
    if ext in RESOURCE_EXTENSIONS:
        return ext
    return ""


def filename_title(url: str) -> str:
    name = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name
    if not name:
        return "未命名资源"
    stem = Path(name).stem or name
    stem = re.sub(r"[_-]+", " ", stem)
    return clean_text(stem) or "未命名资源"


def infer_resource_type(text: str, fmt: str) -> str:
    blob = text.lower()
    rules = [
        ("教材", ["教材", "教科书", "课本"]),
        ("习题", ["练习", "习题", "作业", "可打印"]),
        ("试卷", ["试卷", "测试题", "单元测试"]),
        ("课件", ["课件", "ppt", "pptx"]),
        ("视频", ["视频", "网课", "讲解", "mp4"]),
        ("音频", ["音频", "朗读", "儿歌", "故事", "mp3"]),
        ("图片", ["图片", "图卡", "卡片"]),
        ("百科文章", ["百科", "科普", "知识"]),
        ("讲义", ["讲义", "教案", "素材"]),
    ]
    for resource_type, terms in rules:
        if any(term in blob for term in terms):
            return resource_type
    if fmt in {"ppt", "pptx"}:
        return "课件"
    if fmt in {"mp4", "mov", "avi"}:
        return "视频"
    if fmt in {"mp3", "wav", "m4a"}:
        return "音频"
    if fmt in {"jpg", "png", "webp", "gif"}:
        return "图片"
    if fmt in {"zip", "rar", "7z"}:
        return "压缩包"
    return "文档"


def infer_subject_and_domain(text: str) -> tuple[Any, Any]:
    blob = text.lower()
    if any(term in blob for term in ["数学", "四则", "运算", "分数", "加减乘除"]):
        return "数学", "数学"
    if any(term in blob for term in ["语文", "拼音", "识字", "唐诗", "宋词", "成语"]):
        return "语文", "文学"
    if any(term in blob for term in ["英语", "英文", "自然拼读"]):
        return "英语", "英语"
    if any(term in blob for term in ["百科", "科普", "宇宙", "恐龙"]):
        return None, "百科"
    if any(term in blob for term in ["儿歌", "音乐", "节奏"]):
        return None, "音乐"
    return None, None


def infer_context_field(filters: dict[str, Any], key: str, text: str) -> Any:
    value = filters.get(key)
    if value and str(value).lower() in text.lower():
        return value
    return None


def infer_topic(filters: dict[str, Any], text: str) -> Any:
    topic = filters.get("core_topic") or filters.get("topic")
    if not topic:
        return None
    topic_text = str(topic)
    if topic_text.lower() in text.lower():
        return topic
    parts = [part for part in re.split(r"[\s、,，/]+", topic_text) if part]
    hits = [part for part in parts if part.lower() in text.lower()]
    return topic if hits and len(hits) >= max(1, len(parts) // 2) else None


def metadata_confidence(candidate: dict[str, Any]) -> float:
    fields = ["title", "source_url", "description", "resource_type", "format"]
    present = sum(1 for field in fields if candidate.get(field))
    confidence = present / len(fields)
    raw = candidate.get("raw") or {}
    if raw.get("origin_title"):
        confidence += 0.08
    if candidate.get("title") == "未命名资源":
        confidence -= 0.2
    return round(max(min(confidence, 1.0), 0.0), 2)


def parse_html_resource_links(base_url: str, html_text: str) -> tuple[str, list[dict[str, str]]]:
    parser = LinkParser()
    parser.feed(html_text)
    title = clean_text(" ".join(parser.title_parts))
    resources: list[dict[str, str]] = []
    for link in parser.links:
        url = absolute_url(base_url, link.get("url", ""))
        fmt = normalized_format(extension_for_url(url))
        if fmt:
            resources.append({"url": url, "format": fmt, "text": clean_text(link.get("text"))})
    return title, resources


def profiles_from_site_profile(data: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("site-profile JSON must contain profiles list")
    return [item for item in profiles if isinstance(item, dict)]


def candidate_from_link(profile: dict[str, Any], link: dict[str, Any], rank: int, filters: dict[str, Any], method: str) -> dict[str, Any] | None:
    origin_url = clean_text(profile.get("source_url"))
    raw_url = clean_text(link.get("url"))
    if not raw_url:
        return None
    direct_url = absolute_url(origin_url, raw_url) if origin_url else raw_url
    fmt = normalized_format(clean_text(link.get("format")).lower()) or normalized_format(extension_for_url(direct_url))
    if not fmt:
        return None

    link_text = clean_text(link.get("text"))
    title = link_text or filename_title(direct_url)
    origin_title = clean_text(profile.get("title"))
    description = f"来自 {origin_title}" if origin_title else f"来自 {urllib.parse.urlparse(origin_url or direct_url).netloc}"
    combined = f"{title} {description} {direct_url} {origin_url}"
    subject, learning_domain = infer_subject_and_domain(combined)
    auth_hints = [clean_text(item) for item in profile.get("auth_hints") or [] if clean_text(item)]
    warnings = [clean_text(item) for item in profile.get("warnings") or [] if clean_text(item)]
    if auth_hints and not any("访问限制" in item for item in warnings):
        warnings.append("来源页面可能存在登录、付费或授权限制")
    requires_auth = bool(auth_hints) or any(term in combined for term in AUTH_TERMS)
    host = urllib.parse.urlparse(origin_url or direct_url).netloc.lower()

    candidate = {
        "source": "generic-web-source",
        "source_name": host or "通用网页来源",
        "source_url": direct_url,
        "resource_id": stable_id(direct_url),
        "title": title,
        "description": description,
        "resource_type": infer_resource_type(combined, fmt),
        "format": fmt,
        "stage": infer_context_field(filters, "stage", combined),
        "grade": infer_context_field(filters, "grade", combined),
        "subject": subject,
        "learning_domain": learning_domain,
        "version": infer_context_field(filters, "version", combined),
        "volume": infer_context_field(filters, "volume", combined),
        "topic": infer_topic(filters, combined),
        "provider": host,
        "official": any(hint in combined or hint in host for hint in OFFICIAL_HINTS),
        "downloadable": True,
        "requires_auth": requires_auth,
        "size": None,
        "metadata_confidence": 0.0,
        "raw": {
            "rank": rank,
            "origin_page_url": origin_url,
            "origin_title": origin_title,
            "direct_url": direct_url,
            "host": host,
            "extraction_method": method,
            "profile_strategy": profile.get("crawl_strategy"),
            "warnings": list(dict.fromkeys(warnings)),
        },
    }
    candidate["metadata_confidence"] = metadata_confidence(candidate)
    return candidate


def extract_from_profiles(profiles: list[dict[str, Any]], filters: dict[str, Any], include_non_generic: bool) -> tuple[list[dict[str, Any]], int, int]:
    candidates: list[dict[str, Any]] = []
    links_seen = 0
    skipped = 0
    seen_urls: set[str] = set()
    for profile in profiles:
        strategy = profile.get("crawl_strategy")
        links = profile.get("resource_links") or []
        if strategy != "generic_extract" and not include_non_generic:
            skipped += len(links) or 1
            continue
        if not isinstance(links, list):
            skipped += 1
            continue
        links_seen += len(links)
        for link in links:
            if not isinstance(link, dict):
                skipped += 1
                continue
            candidate = candidate_from_link(profile, link, len(candidates) + 1, filters, "site-profile")
            if not candidate:
                skipped += 1
                continue
            if candidate["source_url"] in seen_urls:
                skipped += 1
                continue
            seen_urls.add(candidate["source_url"])
            candidates.append(candidate)
    return candidates, links_seen, skipped


def run(args: argparse.Namespace) -> int:
    filters = load_json(args.task_json).get("filters", {}) if args.task_json else {}
    if not isinstance(filters, dict):
        filters = {}

    profiles: list[dict[str, Any]]
    if args.site_profile_json:
        site_profile = load_json(args.site_profile_json)
        profiles = profiles_from_site_profile(site_profile)
    elif args.url and args.html_file:
        html_text = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
        title, links = parse_html_resource_links(args.url, html_text)
        profiles = [
            {
                "source_url": args.url,
                "host": urllib.parse.urlparse(args.url).netloc.lower(),
                "title": title,
                "description": "",
                "crawl_strategy": "generic_extract",
                "resource_links": links,
                "auth_hints": [],
                "warnings": [],
            }
        ]
    else:
        print("error: provide --site-profile-json or both --url and --html-file", file=sys.stderr)
        return 2

    candidates, links_seen, skipped = extract_from_profiles(profiles[: args.limit], filters, args.include_non_generic)
    result = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "generic-web-source",
        "query": args.query or "",
        "filters": filters,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "summary": {
            "profiles": len(profiles[: args.limit]),
            "links_seen": links_seen,
            "candidates": len(candidates),
            "skipped": skipped,
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if candidates else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract direct resource candidates from generic web source profiles")
    parser.add_argument("--site-profile-json", help="site-profile/v1 JSON from web-resource-profiler")
    parser.add_argument("--url", help="Origin page URL for local HTML extraction")
    parser.add_argument("--html-file", help="Local HTML file for extraction")
    parser.add_argument("--task-json", help="Optional intent task JSON; filters are used only when supported by evidence")
    parser.add_argument("--query", help="Original user/search query")
    parser.add_argument("--limit", type=int, default=20, help="Maximum profiles to process")
    parser.add_argument("--include-non-generic", action="store_true", help="Also extract direct links from profiles not marked generic_extract")
    parser.add_argument("-o", "--output", help="Write candidate JSON")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
