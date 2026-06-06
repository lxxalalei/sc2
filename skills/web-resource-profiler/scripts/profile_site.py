#!/usr/bin/env python3
"""Profile learning resource site structure."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


RESOURCE_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "jpg", "jpeg", "png", "webp", "gif", "mp3", "wav", "m4a", "mp4", "mov", "zip"}
RESOURCE_TERMS = ["资源", "资料", "课件", "练习题", "习题", "试卷", "下载", "教案", "讲义", "素材", "教材"]
API_TERMS = ["api", "search", "resource", "resources", "content", "catalog", "course", "lesson", "detail", "graphql", "ndrs"]
AUTH_TERMS = ["登录", "会员", "付费", "授权", "购买", "accessToken", "Authorization", "token"]
PAGINATION_TERMS = ["下一页", "上一页", "分页", "page=", "pageNo", "pageIndex", "cursor", "offset"]
RISK_TERMS = ["下载器", "破解", "成人", "博彩", "贷款", "注册机"]


class SiteHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_script = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []
        self.forms: list[dict[str, str]] = []
        self.meta_description = ""
        self.script_text_parts: list[str] = []
        self.current_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "script":
            self.in_script = True
            if data.get("src"):
                self.scripts.append(data["src"])
        elif tag == "link" and data.get("href"):
            self.styles.append(data["href"])
        elif tag == "meta" and data.get("name", "").lower() == "description":
            self.meta_description = data.get("content", "")
        elif tag == "a" and data.get("href"):
            self.current_link = {"url": data["href"], "text": ""}
            self.links.append(self.current_link)
        elif tag == "form":
            self.forms.append({"action": data.get("action", ""), "method": data.get("method", "get")})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.in_script = False
        elif tag == "a":
            self.current_link = None

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if self.in_script:
            self.script_text_parts.append(text)
        else:
            self.text_parts.append(text)
        if self.current_link is not None:
            self.current_link["text"] = (self.current_link.get("text", "") + " " + text).strip()


def norm(value: Any) -> str:
    return str(value or "").strip()


def source_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fetch_html(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "learning-resource-profiler/0.1", "Accept": "text/html,*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def absolute_url(base_url: str, url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(url))


def extension_for_url(url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    if suffix == "jpeg":
        return "jpg"
    return suffix


def extract_resource_links(base_url: str, links: list[dict[str, str]]) -> list[dict[str, str]]:
    resources: list[dict[str, str]] = []
    for link in links:
        url = absolute_url(base_url, link["url"])
        ext = extension_for_url(url)
        if ext in RESOURCE_EXTENSIONS:
            resources.append({"url": url, "format": ext, "text": link.get("text", "")})
    return resources


def extract_api_hints(text: str, base_url: str) -> list[str]:
    hints: list[str] = []
    patterns = [
        r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+",
        r"['\"]((?:/|//)[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{3,160})['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1) if match.lastindex else match.group(0)
            if any(term in value.lower() for term in API_TERMS):
                hints.append(absolute_url(base_url, value))
    return list(dict.fromkeys(hints))[:40]


def link_hints(base_url: str, links: list[dict[str, str]], terms: list[str]) -> list[str]:
    results = []
    for link in links:
        blob = f"{link.get('url', '')} {link.get('text', '')}".lower()
        if any(term.lower() in blob for term in terms):
            results.append(absolute_url(base_url, link["url"]))
    return list(dict.fromkeys(results))[:30]


def resource_format_hints(resource_links: list[dict[str, str]], text: str) -> list[str]:
    hints = [item["format"] for item in resource_links if item.get("format")]
    if "m3u8" in text.lower() or "视频" in text:
        hints.append("video")
    if "音频" in text or "mp3" in text.lower():
        hints.append("audio")
    return list(dict.fromkeys(hints))


def resource_type_hints(text: str) -> list[str]:
    rules = [
        ("教材", ["教材", "教科书", "课本"]),
        ("习题", ["练习题", "习题", "作业"]),
        ("试卷", ["试卷", "测试题"]),
        ("课件", ["课件", "ppt", "pptx"]),
        ("视频", ["视频", "网课", "播放"]),
        ("音频", ["音频", "朗读", "儿歌"]),
        ("百科文章", ["百科", "科普", "知识"]),
    ]
    text_lower = text.lower()
    return [name for name, terms in rules if any(term.lower() in text_lower for term in terms)]


def classify_site(parser: SiteHTMLParser, html_text: str, resource_links: list[dict[str, str]], api_hints: list[str]) -> str:
    text = " ".join(parser.text_parts)
    lower_html = html_text.lower()
    if "m3u8" in lower_html or any("视频" in part for part in parser.text_parts):
        return "media_page"
    if len(resource_links) >= 2:
        return "static_resource_page"
    if api_hints and ("id=\"root" in lower_html or "id=root" in lower_html or "chunk-" in lower_html or "/js/app" in lower_html):
        return "spa_app"
    if len(link_hints("", parser.links, ["detail", "course", "resource", "page=", "list"])) >= 3:
        return "resource_listing"
    if any(term in text for term in ["如何", "方法", "指南", "介绍", "科普"]) and not resource_links:
        return "article_page"
    return "unknown"


def strategy_for(site_type: str, resource_links: list[dict[str, str]], api_hints: list[str], auth_hints: list[str], warnings: list[str]) -> str:
    if any("风险词" in item for item in warnings):
        return "reject"
    if site_type == "static_resource_page" and resource_links:
        return "generic_extract"
    if site_type == "spa_app" and api_hints:
        return "dedicated_source_skill"
    if site_type in {"resource_listing", "media_page"}:
        return "profile_deeper"
    if auth_hints and not resource_links:
        return "profile_deeper"
    if site_type == "article_page":
        return "keep_as_web_candidate"
    return "keep_as_web_candidate"


def score_profile(site_type: str, strategy: str, resource_links: list[dict[str, str]], api_hints: list[str], auth_hints: list[str], warnings: list[str]) -> float:
    score = {
        "static_resource_page": 7.0,
        "resource_listing": 6.5,
        "spa_app": 7.5,
        "media_page": 6.0,
        "article_page": 3.0,
        "unknown": 2.0,
    }.get(site_type, 2.0)
    score += min(len(resource_links), 5) * 0.6
    score += min(len(api_hints), 5) * 0.4
    if strategy == "dedicated_source_skill":
        score += 1.0
    if auth_hints:
        score -= 1.0
    if warnings:
        score -= min(len(warnings), 3) * 1.5
    return round(max(min(score, 10.0), 0.0), 2)


def profile_html(source_url: str, html_text: str, source: dict[str, Any] | None = None) -> dict[str, Any]:
    parser = SiteHTMLParser()
    parser.feed(html_text)
    text = " ".join(parser.text_parts)
    script_text = " ".join(parser.script_text_parts)
    combined = f"{text} {script_text} {' '.join(parser.scripts)}"
    parsed = urllib.parse.urlparse(source_url)
    resource_links = extract_resource_links(source_url, parser.links)
    api_hints = extract_api_hints(combined, source_url)
    script_hints = [absolute_url(source_url, item) for item in parser.scripts][:30]
    pagination_hints = link_hints(source_url, parser.links, PAGINATION_TERMS)
    detail_hints = link_hints(source_url, parser.links, ["detail", "详情", "course", "resource", "content", "lesson"])
    auth_hints = [term for term in AUTH_TERMS if term in combined]
    risk_hits = [term for term in RISK_TERMS if term in combined]
    warnings = [f"包含风险词：{term}" for term in risk_hits]
    if auth_hints:
        warnings.append("页面可能存在登录、付费或授权限制")
    site_type = classify_site(parser, html_text, resource_links, api_hints)
    strategy = strategy_for(site_type, resource_links, api_hints, auth_hints, warnings)
    score = score_profile(site_type, strategy, resource_links, api_hints, auth_hints, warnings)
    reasons: list[str] = []
    if resource_links:
        reasons.append("页面包含可直接识别的资源链接")
    if api_hints:
        reasons.append("页面或脚本包含疑似 API 线索")
    if pagination_hints:
        reasons.append("页面包含分页线索")
    if detail_hints:
        reasons.append("页面包含详情页线索")
    if site_type == "spa_app":
        reasons.append("页面具有 SPA 前端应用特征")
    return {
        "source_id": source.get("source_id") if source else source_id(source_url),
        "source_url": source_url,
        "host": parsed.netloc.lower(),
        "title": " ".join(parser.title_parts) or (source or {}).get("title", ""),
        "description": parser.meta_description or (source or {}).get("description", ""),
        "site_type": site_type,
        "crawl_strategy": strategy,
        "score": score,
        "resource_links": resource_links[:50],
        "api_hints": api_hints,
        "script_hints": script_hints,
        "pagination_hints": pagination_hints,
        "detail_link_hints": detail_hints,
        "auth_hints": list(dict.fromkeys(auth_hints)),
        "resource_format_hints": resource_format_hints(resource_links, combined),
        "resource_type_hints": resource_type_hints(combined),
        "reasons": list(dict.fromkeys(reasons)),
        "warnings": list(dict.fromkeys(warnings)),
        "raw": {
            "source": source or {},
            "link_count": len(parser.links),
            "form_count": len(parser.forms),
            "script_count": len(parser.scripts),
            "text_length": len(text),
        },
    }


def sources_from_discovery(path: str) -> list[dict[str, Any]]:
    data = load_json(path)
    sources = data.get("sources") or []
    if not isinstance(sources, list):
        raise ValueError("discovery sources must be a list")
    return [item for item in sources if isinstance(item, dict) and item.get("source_url")]


def run(args: argparse.Namespace) -> int:
    sources: list[dict[str, Any]]
    if args.discovery_json:
        sources = sources_from_discovery(args.discovery_json)
    elif args.url:
        sources = [{"source_url": args.url, "source_id": source_id(args.url)}]
    else:
        print("error: provide --url or --discovery-json", file=sys.stderr)
        return 2

    profiles: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for source in sources[: args.limit]:
        url = norm(source.get("source_url"))
        try:
            if args.html_file:
                html_text = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
            else:
                html_text = fetch_html(url, args.timeout)
            profiles.append(profile_html(url, html_text, source))
        except Exception as exc:
            failures.append({"source_url": url, "error": str(exc)})

    result = {
        "site_profile_schema": "site-profile/v1",
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "profiles": profiles,
        "failures": failures,
        "summary": {
            "input": len(sources[: args.limit]),
            "profiled": len(profiles),
            "failed": len(failures),
            "dedicated_source_recommended": sum(1 for item in profiles if item.get("crawl_strategy") == "dedicated_source_skill"),
            "generic_extract_recommended": sum(1 for item in profiles if item.get("crawl_strategy") == "generic_extract"),
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if profiles else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile resource site structure")
    parser.add_argument("--url", help="Source URL to profile")
    parser.add_argument("--discovery-json", help="resource-source-discovery output JSON")
    parser.add_argument("--html-file", help="Use local HTML file instead of fetching URL")
    parser.add_argument("--limit", type=int, default=5, help="Maximum sources to profile")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds")
    parser.add_argument("-o", "--output", help="Write site profile JSON")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
