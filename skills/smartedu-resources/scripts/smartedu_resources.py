#!/usr/bin/env python3
"""Normalize SmartEdu platform resources into learning resource candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LIBRARY_LIST_URL = "https://api.ykt.cbern.com.cn/zxx/api_static/data/6_6_6/librarylist.json"
SEARCH_URLS = (
    "https://resource-gateway.ykt.eduyun.cn/resources/combine/search",
    "https://resource-gateway.ykt.eduyun.cn/resources/aggregate",
)
DETAIL_URLS = (
    "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{catalog}/details/{id}.json",
    "https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/resources/{catalog}/details/{id}.json",
)
DETAIL_PAGE = (
    "https://basic.smartedu.cn/{catalog}/detail?"
    "contentType={content_type}&contentId={id}&catalogType={catalog}&subCatalog={sub_catalog}"
)
PRIVATE_HOST = "https://r1-ndr-private.ykt.cbern.com.cn"
PUBLIC_HOSTS = (
    "https://r1-ndr.ykt.cbern.com.cn",
    "https://r2-ndr.ykt.cbern.com.cn",
    "https://r3-ndr.ykt.cbern.com.cn",
)
PRIVATE_NDR_RE = re.compile(r"https://r[123]-ndr-private\.ykt\.cbern\.com\.cn")
TAG_DIMENSIONS = {
    "zxxxd": "stage",
    "zxxxk": "subject",
    "zxxnj": "grade",
    "zxxbb": "version",
    "zxxcc": "volume",
}


def norm(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_output(path: str | None, data: Any) -> None:
    output = json.dumps(data, ensure_ascii=False, indent=2)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


def parse_extra_headers(values: list[str] | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    raw_values = list(values or [])
    env_headers = os.environ.get("SMARTEDU_HEADERS")
    if env_headers:
        raw_values.extend(part.strip() for part in env_headers.splitlines() if part.strip())
    for value in raw_values:
        if ":" not in value:
            raise ValueError("--header must use 'Name: value' format")
        name, header_value = value.split(":", 1)
        name = name.strip()
        header_value = header_value.strip()
        if name and header_value:
            headers[name] = header_value
    return headers


def build_headers(access_token: str | None = None, cookie: str | None = None, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 smartedu-resources/0.1",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://basic.smartedu.cn/",
    }
    authorization = os.environ.get("SMARTEDU_AUTHORIZATION")
    cookie = cookie or os.environ.get("SMARTEDU_COOKIE")
    if authorization:
        headers["Authorization"] = authorization
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        headers["accessToken"] = access_token
    if cookie:
        headers["Cookie"] = cookie
    headers.update(extra_headers or {})
    headers["Content-Type"] = "application/json;charset=UTF-8"
    return headers


def request_json(
    url: str,
    access_token: str | None = None,
    timeout: int = 20,
    retries: int = 2,
    payload: Any = None,
    cookie: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            data = None
            if payload is not None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = Request(url, data=data, headers=build_headers(access_token, cookie=cookie, extra_headers=extra_headers))
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last_error}")


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def safe_detail_page(detail: dict[str, Any], catalog: str, sub_catalog: str) -> str:
    resource_id = norm(detail.get("id"))
    content_type = norm(detail.get("resource_type_code")) or "resource"
    return DETAIL_PAGE.format(
        catalog=urllib.parse.quote(catalog or "syncClassroom"),
        content_type=urllib.parse.quote(content_type),
        id=urllib.parse.quote(resource_id),
        sub_catalog=urllib.parse.quote(sub_catalog or ""),
    )


def provider_name(detail: dict[str, Any]) -> str:
    providers = detail.get("provider_list") or []
    names = [norm(item.get("name")) for item in providers if isinstance(item, dict) and norm(item.get("name"))]
    return "/".join(names) if names else "国家中小学智慧教育平台"


def tags_by_dimension(detail: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for tag in detail.get("tag_list") or []:
        if not isinstance(tag, dict):
            continue
        dim = TAG_DIMENSIONS.get(str(tag.get("tag_dimension_id")))
        if dim and dim not in values:
            values[dim] = norm(tag.get("tag_name"))
    return values


def requirement_value(item: dict[str, Any], name: str) -> Any:
    custom = item.get("custom_properties") or {}
    for req in custom.get("requirements") or []:
        if isinstance(req, dict) and str(req.get("name")).lower() == name.lower():
            return req.get("value")
    return None


def quote_url_path(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:")
    return urllib.parse.urlunparse(parsed._replace(path=path))


def storage_urls(item: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    storage = norm(item.get("ti_storage"))
    if storage.startswith("cs_path:${ref-path}"):
        suffix = storage.replace("cs_path:${ref-path}", "")
        candidates.append(PRIVATE_HOST + urllib.parse.quote(urllib.parse.unquote(suffix), safe="/:"))
        for host in PUBLIC_HOSTS:
            candidates.append(host + urllib.parse.quote(urllib.parse.unquote(suffix), safe="/:"))
    for url in item.get("ti_storages") or []:
        if not isinstance(url, str) or not url:
            continue
        candidates.append(quote_url_path(url))
        candidates.append(quote_url_path(PRIVATE_NDR_RE.sub(PUBLIC_HOSTS[0], url)))
    unique: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def item_requires_auth(item: dict[str, Any], urls: list[str]) -> bool:
    custom = item.get("custom_properties") or {}
    if custom.get("identification") is True:
        return True
    return any("ndr-private" in url for url in urls)


def normalized_format(item: dict[str, Any], url: str) -> str:
    fmt = norm(item.get("ti_format") or item.get("lc_ti_format")).lower()
    if fmt in {"application/x-mpegurl", "application/vnd.apple.mpegurl"}:
        return "m3u8"
    if "/" in fmt:
        fmt = fmt.rsplit("/", 1)[-1]
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    if fmt in {"folder", "source", ""} and suffix:
        fmt = suffix
    if fmt == "jpeg":
        return "jpg"
    return fmt or suffix or "unknown"


def resource_type_for(fmt: str, item: dict[str, Any], detail: dict[str, Any]) -> str:
    if fmt in {"ppt", "pptx"}:
        return "课件"
    if fmt in {"jpg", "png", "webp", "gif", "bmp"}:
        return "图片"
    if fmt in {"pdf", "doc", "docx", "txt", "xls", "xlsx"}:
        return "文档"
    if fmt in {"zip", "rar", "7z"}:
        return "压缩包"
    if fmt in {"m3u8", "mp4", "mov", "avi", "webm"}:
        return "视频"
    if fmt in {"mp3", "wav", "m4a", "aac", "flac", "ogg"}:
        return "音频"
    blob = " ".join(
        [
            fmt,
            norm(item.get("ti_file_flag")),
            norm(item.get("lc_ti_format")),
            norm(detail.get("resource_type_code_name")),
            norm(detail.get("title")),
        ]
    ).lower()
    if "video" in blob or "视频" in blob:
        return "视频"
    if "audio" in blob or "音频" in blob:
        return "音频"
    if "image" in blob:
        return "图片"
    if any(term in blob for term in ["习题", "作业"]):
        return "习题"
    if any(term in blob for term in ["试卷", "考试"]):
        return "试卷"
    return "文档"


def metadata_confidence(candidate: dict[str, Any]) -> float:
    fields = ["title", "source_url", "resource_type", "format", "provider"]
    return round(sum(1 for field in fields if candidate.get(field)) / len(fields), 2)


def first_value(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def parse_tab_codes(values: list[str] | None) -> list[str]:
    tab_codes: list[str] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part and part not in tab_codes:
                tab_codes.append(part)
    return tab_codes or ["qualityCourse", "prepareLesson", "questions", "examinationPapers", "teachingKnMicroLesson"]


def search_payload(args: argparse.Namespace, filters: dict[str, Any]) -> dict[str, Any]:
    query = args.query or norm(filters.get("query") or filters.get("core_topic") or filters.get("subject"))
    return {
        "identity": args.identity,
        "identity_code": args.identity_code,
        "keyword": query,
        "tab_codes": parse_tab_codes(args.tab_code),
        "resource_search_type": args.search_type,
        "cross_tenant": args.cross_tenant,
        "duplicate_filter": True,
        "search_order": {"field": args.order_field, "direction": args.order_direction},
        "search_fields": [],
        "offset": args.offset,
        "limit": args.limit,
        "combine_intentions": True,
        "combine_resources": True,
        "tags": [],
        "origin": args.origin,
    }


def candidate_lists(data: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            dicts = [item for item in node if isinstance(item, dict)]
            if dicts and any(is_search_item_like(item) for item in dicts):
                found.append(dicts)
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(data)
    return found


def is_search_item_like(item: dict[str, Any]) -> bool:
    has_id = any(item.get(key) for key in ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])
    has_title = any(item.get(key) for key in ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"])
    has_type = any(item.get(key) for key in ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "resource_type", "resourceType", "content_type", "contentType"])
    return bool(has_id and (has_title or has_type))


def extract_search_items(data: Any, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [item for group in candidate_lists(data) for item in group]:
        if not is_search_item_like(row):
            continue
        key = norm(first_value(row, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"]))
        title = norm(first_value(row, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"]))
        fingerprint = f"{key}:{title}"
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        items.append(row)
        if len(items) >= limit:
            break
    return items


def infer_format_from_item(item: dict[str, Any], url: str) -> str:
    fmt = norm(first_value(item, ["format", "file_format", "fileFormat", "resource_format", "resourceFormat", "ti_format"])).lower()
    if "/" in fmt:
        fmt = fmt.rsplit("/", 1)[-1]
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    return ("jpg" if fmt == "jpeg" else fmt) or suffix or "网页"


def detail_page_from_search_item(item: dict[str, Any]) -> str:
    explicit = norm(first_value(item, ["url", "web_url", "webUrl", "href", "detail_url", "detailUrl", "share_url", "shareUrl"]))
    if explicit.startswith("http"):
        return explicit
    resource_id = norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"]))
    catalog = norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"])) or "syncClassroom"
    sub_catalog = norm(first_value(item, ["sub_catalog", "subCatalog", "sub_catalog_code", "subCatalogCode"]))
    content_type = norm(first_value(item, ["content_type", "contentType", "resource_type", "resourceType", "resource_type_code", "resourceTypeCode"])) or "resource"
    return DETAIL_PAGE.format(
        catalog=urllib.parse.quote(catalog),
        content_type=urllib.parse.quote(content_type),
        id=urllib.parse.quote(resource_id),
        sub_catalog=urllib.parse.quote(sub_catalog),
    )


def search_item_to_candidate(item: dict[str, Any], query: str, filters: dict[str, Any]) -> dict[str, Any]:
    source_url = detail_page_from_search_item(item)
    fmt = infer_format_from_item(item, source_url)
    title = norm(first_value(item, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"])) or "SmartEdu 资源"
    catalog = norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"]))
    resource_id = norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])) or stable_id(title + source_url)
    candidate = {
        "source": "smartedu-resources",
        "source_name": "国家中小学智慧教育平台",
        "source_url": source_url,
        "resource_id": f"smartedu-search:{resource_id}",
        "title": title,
        "description": norm(first_value(item, ["description", "summary", "intro", "content", "snippet", "global_description"])),
        "resource_type": norm(first_value(item, ["resource_type_name", "resourceTypeName", "content_type_name", "contentTypeName"])) or resource_type_for(fmt, {}, item),
        "format": fmt,
        "stage": norm(first_value(item, ["stage", "phase", "school_section"])) or filters.get("stage"),
        "grade": norm(first_value(item, ["grade", "grade_name", "gradeName"])) or filters.get("grade"),
        "subject": norm(first_value(item, ["subject", "subject_name", "subjectName"])) or filters.get("subject"),
        "learning_domain": norm(first_value(item, ["subject", "subject_name", "subjectName"])) or filters.get("learning_domain") or filters.get("subject"),
        "version": norm(first_value(item, ["version", "version_name", "versionName"])) or filters.get("version"),
        "volume": norm(first_value(item, ["volume", "book", "book_name", "bookName"])) or filters.get("volume"),
        "topic": filters.get("core_topic") or query,
        "provider": norm(first_value(item, ["provider", "provider_name", "providerName", "source_name", "sourceName"])) or "国家中小学智慧教育平台",
        "official": True,
        "downloadable": False,
        "requires_auth": False,
        "metadata_confidence": 0.0,
        "raw": {
            "detail_page": source_url,
            "smartedu_catalog": catalog,
            "smartedu_search_item": item,
            "warnings": ["搜索结果候选尚未解析详情文件项"],
        },
    }
    candidate["metadata_confidence"] = metadata_confidence(candidate)
    return candidate


def search_item_identity(item: dict[str, Any]) -> dict[str, str]:
    return {
        "resource_id": norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])),
        "catalog": norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"])) or "syncClassroom",
        "sub_catalog": norm(first_value(item, ["sub_catalog", "subCatalog", "sub_catalog_code", "subCatalogCode"])),
    }


def load_detail_from_dir(detail_dir: str | None, identity: dict[str, str]) -> dict[str, Any] | None:
    if not detail_dir:
        return None
    root = Path(detail_dir)
    resource_id = identity["resource_id"]
    catalog = identity["catalog"]
    candidates = [
        root / f"{resource_id}.json",
        root / f"{catalog}-{resource_id}.json",
        root / catalog / f"{resource_id}.json",
    ]
    for path in candidates:
        if path.exists():
            data = load_json(str(path))
            if isinstance(data, dict):
                return data
    return None


def detail_for_search_item(
    item: dict[str, Any],
    args: argparse.Namespace,
    access_token: str | None,
    extra_headers: dict[str, str],
) -> tuple[dict[str, Any] | None, dict[str, str], str | None]:
    identity = search_item_identity(item)
    if not identity["resource_id"]:
        return None, identity, "missing resource id"
    cached = load_detail_from_dir(args.detail_dir, identity)
    if cached is not None:
        return cached, identity, None
    if args.offline_details_only:
        return None, identity, "detail not found in detail dir"
    try:
        return fetch_detail(identity["resource_id"], identity["catalog"], access_token, cookie=args.cookie, extra_headers=extra_headers), identity, None
    except Exception as exc:
        return None, identity, str(exc)


def candidate_title(detail: dict[str, Any], item: dict[str, Any], fmt: str) -> str:
    title = norm(detail.get("title") or detail.get("global_title"))
    flag = norm(item.get("ti_file_flag"))
    if flag and flag not in {"source", "href", "href-m3u8"}:
        return f"{title} - {flag}"
    if fmt and fmt != "unknown":
        return f"{title} - {fmt.upper()}"
    return title or norm(detail.get("id")) or "SmartEdu 资源"


def candidates_from_detail(detail: dict[str, Any], catalog: str, sub_catalog: str, filters: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], int, int]:
    filters = filters or {}
    dimensions = tags_by_dimension(detail)
    candidates: list[dict[str, Any]] = []
    skipped = 0
    detail_page = safe_detail_page(detail, catalog or norm(detail.get("catalog")), sub_catalog)
    provider = provider_name(detail)
    items = detail.get("ti_items") or []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            skipped += 1
            continue
        urls = storage_urls(item)
        if not urls:
            skipped += 1
            continue
        primary_url = urls[0]
        fmt = normalized_format(item, primary_url)
        if fmt in {"folder", "unknown"} and not item.get("lc_ti_format"):
            skipped += 1
            continue
        requires_auth = item_requires_auth(item, urls)
        warnings = ["可能需要 SmartEdu 登录授权"] if requires_auth else []
        resource_type = resource_type_for(fmt, item, detail)
        candidate = {
            "source": "smartedu-resources",
            "source_name": "国家中小学智慧教育平台",
            "source_url": primary_url,
            "resource_id": f"{norm(detail.get('id'))}:{index}:{stable_id(primary_url)}",
            "title": candidate_title(detail, item, fmt),
            "description": norm(detail.get("description") or detail.get("global_description")),
            "resource_type": resource_type,
            "format": fmt,
            "stage": dimensions.get("stage") or filters.get("stage"),
            "grade": dimensions.get("grade") or filters.get("grade"),
            "subject": dimensions.get("subject") or filters.get("subject"),
            "learning_domain": dimensions.get("subject") or filters.get("learning_domain"),
            "version": dimensions.get("version") or filters.get("version"),
            "volume": dimensions.get("volume") or filters.get("volume"),
            "topic": filters.get("core_topic") or filters.get("topic"),
            "provider": provider,
            "official": True,
            "downloadable": fmt not in {"folder", "unknown"},
            "requires_auth": requires_auth,
            "size": requirement_value(item, "FileSize"),
            "metadata_confidence": 0.0,
            "raw": {
                "detail_page": detail_page,
                "smartedu_detail_id": detail.get("id"),
                "smartedu_catalog": catalog,
                "smartedu_sub_catalog": sub_catalog,
                "smartedu_item_index": index,
                "smartedu_item": item,
                "url_candidates": urls,
                "warnings": warnings,
            },
        }
        candidate["metadata_confidence"] = metadata_confidence(candidate)
        candidates.append(candidate)
    return candidates, len(items), skipped


def flatten_catalogs(items: list[dict[str, Any]], parent: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = norm(item.get("name") or item.get("title") or item.get("catalog_name"))
        catalog = norm(item.get("catalog") or item.get("id") or item.get("code"))
        is_textbook = item.get("type") == "tchMaterial" or catalog == "tchMaterial"
        row = {
            "id": item.get("id"),
            "title": title,
            "catalog": catalog,
            "catalog_name": item.get("catalog_name") or title,
            "type": item.get("type") or item.get("code"),
            "resource_family": "教材" if is_textbook else "通用资源",
            "sub_catalog": item.get("sub_catalog"),
            "sub_catalog_name": item.get("sub_catalog_name"),
            "parent": parent,
            "known_skill": "smartedu-resources",
            "internal_adapter": "tchMaterial" if is_textbook else "",
            "external": bool(item.get("h5_url") or (item.get("page_mode") or {}).get("type") == "outer_link"),
            "raw": item,
        }
        rows.append(row)
        children = item.get("child")
        if isinstance(children, list):
            rows.extend(flatten_catalogs(children, title or parent))
    return rows


def run_list_catalogs(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    if args.library_list_json:
        data = load_json(args.library_list_json)
    else:
        data = request_json(LIBRARY_LIST_URL, access_token=access_token, cookie=args.cookie, extra_headers=extra_headers)
    if not isinstance(data, list):
        raise ValueError("library list must be a JSON list")
    catalogs = flatten_catalogs(data)
    result = {
        "catalog_profile_schema": "smartedu-catalog-profile/v1",
        "source_skill": "smartedu-resources",
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "catalogs": catalogs,
        "summary": {
            "catalogs": len(catalogs),
            "resource_catalogs": sum(1 for item in catalogs if item.get("known_skill") == "smartedu-resources"),
            "external_catalogs": sum(1 for item in catalogs if item.get("external")),
            "textbook_catalogs": sum(1 for item in catalogs if item.get("internal_adapter") == "tchMaterial"),
            "auth_context": bool(access_token or args.cookie or extra_headers or os.environ.get("SMARTEDU_COOKIE") or os.environ.get("SMARTEDU_AUTHORIZATION")),
        },
    }
    write_output(args.output, result)
    return 0


def fetch_detail(
    resource_id: str,
    catalog: str,
    access_token: str | None,
    cookie: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    for template in DETAIL_URLS:
        url = template.format(catalog=urllib.parse.quote(catalog), id=urllib.parse.quote(resource_id))
        try:
            return request_json(url, access_token=access_token, cookie=cookie, extra_headers=extra_headers)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("; ".join(errors))


def load_task_filters(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data = load_json(path)
    if isinstance(data, dict):
        return data.get("filters") or data.get("intent") or {}
    return {}


def run_candidates_from_detail(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    details: list[dict[str, Any]] = []
    if args.detail_json:
        for path in args.detail_json:
            data = load_json(path)
            if isinstance(data, list):
                details.extend(item for item in data if isinstance(item, dict))
            elif isinstance(data, dict):
                details.append(data)
    elif args.resource_id and args.catalog:
        details.append(fetch_detail(args.resource_id, args.catalog, access_token, cookie=args.cookie, extra_headers=extra_headers))
    else:
        print("error: provide --detail-json or both --catalog and --resource-id", file=sys.stderr)
        return 2

    filters = load_task_filters(args.task_json)
    all_candidates: list[dict[str, Any]] = []
    items_seen = 0
    skipped = 0
    for detail in details[: args.limit]:
        candidates, seen, failed = candidates_from_detail(detail, args.catalog or "syncClassroom", args.sub_catalog or "", filters)
        all_candidates.extend(candidates)
        items_seen += seen
        skipped += failed

    result = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "smartedu-resources",
        "query": args.query or "",
        "filters": filters,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": all_candidates,
        "summary": {
            "details": len(details[: args.limit]),
            "items_seen": items_seen,
            "candidates": len(all_candidates),
            "skipped": skipped,
            "auth_context": bool(access_token or args.cookie or extra_headers or os.environ.get("SMARTEDU_COOKIE") or os.environ.get("SMARTEDU_AUTHORIZATION")),
        },
    }
    write_output(args.output, result)
    return 0 if all_candidates else 1


def fetch_search_results(args: argparse.Namespace, filters: dict[str, Any]) -> Any:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    payload = search_payload(args, filters)
    if args.search_url:
        return request_json(args.search_url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers)
    errors: list[str] = []
    for url in SEARCH_URLS:
        try:
            return request_json(url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("; ".join(errors))


def run_search_resources(args: argparse.Namespace) -> int:
    filters = load_task_filters(args.task_json)
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    query = args.query or norm(filters.get("query") or filters.get("core_topic") or filters.get("subject"))
    if args.search_response_json:
        data = load_json(args.search_response_json)
    else:
        data = fetch_search_results(args, filters)
    items = extract_search_items(data, args.limit)
    candidates: list[dict[str, Any]] = []
    details_fetched = 0
    detail_failures: list[dict[str, str]] = []
    detail_items_seen = 0
    detail_items_skipped = 0
    if args.fetch_details:
        for item in items:
            detail, identity, error = detail_for_search_item(item, args, access_token, extra_headers)
            if detail is None:
                fallback = search_item_to_candidate(item, query, filters)
                fallback.setdefault("raw", {}).setdefault("warnings", []).append(f"详情追踪失败：{error or 'unknown error'}")
                candidates.append(fallback)
                detail_failures.append({"resource_id": identity.get("resource_id", ""), "catalog": identity.get("catalog", ""), "error": error or "unknown error"})
                continue
            detail_candidates, seen, skipped = candidates_from_detail(detail, identity["catalog"], identity["sub_catalog"], filters)
            details_fetched += 1
            detail_items_seen += seen
            detail_items_skipped += skipped
            if detail_candidates:
                candidates.extend(detail_candidates)
            else:
                fallback = search_item_to_candidate(item, query, filters)
                fallback.setdefault("raw", {}).setdefault("warnings", []).append("详情已获取但未解析出文件项")
                candidates.append(fallback)
    else:
        candidates = [search_item_to_candidate(item, query, filters) for item in items]
    result = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "smartedu-resources",
        "query": query,
        "filters": filters,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "summary": {
            "search_items_seen": len(items),
            "candidates": len(candidates),
            "fetch_details": bool(args.fetch_details),
            "details_fetched": details_fetched,
            "detail_items_seen": detail_items_seen,
            "detail_items_skipped": detail_items_skipped,
            "detail_failures": len(detail_failures),
            "online": not bool(args.search_response_json),
            "endpoint": args.search_url or SEARCH_URLS[0],
            "auth_context": bool(access_token or args.cookie or extra_headers or os.environ.get("SMARTEDU_COOKIE") or os.environ.get("SMARTEDU_AUTHORIZATION")),
            "note": "搜索候选用于分析和排序；下载前应继续抓取详情并解析 ti_items。",
        },
    }
    if detail_failures:
        result["detail_failures"] = detail_failures
    write_output(args.output, result)
    return 0 if candidates else 1


def append_arg(command: list[str], flag: str, value: Any) -> None:
    if value not in (None, ""):
        command.extend([flag, str(value)])


def run_textbook_candidates(args: argparse.Namespace) -> int:
    fetch_script = Path(__file__).resolve().parents[2] / "smartedu-textbooks" / "scripts" / "fetch_textbooks.py"
    if not fetch_script.exists():
        print(f"error: missing internal adapter {fetch_script}", file=sys.stderr)
        return 2

    command = [
        sys.executable,
        str(fetch_script),
        "--list-only",
        "--work-dir",
        args.work_dir,
        "--show",
        str(args.show),
    ]
    append_arg(command, "--stage", args.stage)
    append_arg(command, "--grade", args.grade)
    append_arg(command, "--subject", args.subject)
    append_arg(command, "--version", args.version)
    append_arg(command, "--volume", args.volume)
    append_arg(command, "--query", args.query)
    append_arg(command, "--limit", args.limit)
    if args.sync:
        command.append("--sync")

    completed = subprocess.run(command, text=True, capture_output=True, cwd=str(Path(__file__).resolve().parents[3]))
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr.strip(), file=sys.stderr)
        if completed.stdout:
            print(completed.stdout.strip(), file=sys.stderr)
        return completed.returncode

    data = json.loads(completed.stdout)
    data["source_skill"] = "smartedu-resources"
    data["resource_family"] = "教材"
    data["internal_adapter"] = "tchMaterial"
    for candidate in data.get("candidates") or []:
        candidate["source"] = "smartedu-resources"
        raw = candidate.setdefault("raw", {})
        if isinstance(raw, dict):
            raw["internal_adapter"] = "tchMaterial"
            raw["smartedu_catalog"] = "tchMaterial"
    write_output(args.output, data)
    return 0 if data.get("candidates") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SmartEdu generic resource source")
    sub = parser.add_subparsers(dest="command", required=True)

    catalogs = sub.add_parser("list-catalogs", help="输出 SmartEdu 栏目画像")
    catalogs.add_argument("--library-list-json", help="本地 librarylist JSON；省略时抓取官方公开配置")
    catalogs.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    catalogs.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    catalogs.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    catalogs.add_argument("-o", "--output", help="写入 JSON 文件")
    catalogs.set_defaults(func=run_list_catalogs)

    detail = sub.add_parser("candidates-from-detail", help="从 SmartEdu 详情 JSON 输出标准候选")
    detail.add_argument("--detail-json", action="append", help="本地 SmartEdu detail JSON，可重复")
    detail.add_argument("--catalog", help="栏目，例如 qualityCourse、syncClassroom、family")
    detail.add_argument("--sub-catalog", help="子栏目，例如 course、prepare_lesson")
    detail.add_argument("--resource-id", help="资源 ID；与 --catalog 一起尝试抓取详情")
    detail.add_argument("--task-json", help="可选任务 JSON，用于传递 filters")
    detail.add_argument("--query", help="原始查询")
    detail.add_argument("--limit", type=int, default=50, help="最多处理详情数量")
    detail.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    detail.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    detail.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    detail.add_argument("-o", "--output", help="写入 JSON 文件")
    detail.set_defaults(func=run_candidates_from_detail)

    search = sub.add_parser("search-resources", help="搜索 SmartEdu 资源并输出标准候选")
    search.add_argument("--query", help="搜索关键词；省略时从 --task-json 的 filters 中推断")
    search.add_argument("--task-json", help="可选任务 JSON，用于传递 filters")
    search.add_argument("--tab-code", action="append", help="SmartEdu tab_code，可重复或逗号分隔")
    search.add_argument("--search-response-json", help="本地 SmartEdu 搜索响应 JSON；用于离线归一化测试")
    search.add_argument("--search-url", help="自定义 SmartEdu 搜索接口 URL")
    search.add_argument("--fetch-details", action="store_true", help="对搜索候选继续追踪详情 JSON 并解析 ti_items")
    search.add_argument("--detail-dir", help="本地详情 JSON 目录；支持 {id}.json、{catalog}-{id}.json、{catalog}/{id}.json")
    search.add_argument("--offline-details-only", action="store_true", help="只使用 --detail-dir，不联网抓取缺失详情")
    search.add_argument("--identity", default="GUEST", help="SmartEdu identity，默认 GUEST")
    search.add_argument("--identity-code", default="GUEST", help="SmartEdu identity_code，默认 GUEST")
    search.add_argument("--search-type", default="resource", help="resource_search_type，默认 resource")
    search.add_argument("--origin", default="basic", help="SmartEdu origin，默认 basic")
    search.add_argument("--order-field", default="default", help="排序字段")
    search.add_argument("--order-direction", default="desc", help="排序方向")
    search.add_argument("--offset", type=int, default=0, help="分页 offset")
    search.add_argument("--limit", type=int, default=12, help="最多输出候选数量")
    search.add_argument("--cross-tenant", action="store_true", help="允许跨租户搜索")
    search.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    search.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    search.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    search.add_argument("-o", "--output", help="写入 JSON 文件")
    search.set_defaults(func=run_search_resources)

    textbooks = sub.add_parser("textbook-candidates", help="输出 SmartEdu 站内教材候选")
    textbooks.add_argument("--stage", help="学段，例如 小学")
    textbooks.add_argument("--grade", help="年级，例如 三年级")
    textbooks.add_argument("--subject", help="学科，例如 数学")
    textbooks.add_argument("--version", help="版本，例如 人教版")
    textbooks.add_argument("--volume", help="册次，例如 上册")
    textbooks.add_argument("--query", help="额外关键词")
    textbooks.add_argument("--limit", type=int, help="限制内部索引匹配数量")
    textbooks.add_argument("--show", type=int, default=20, help="最多输出候选数量")
    textbooks.add_argument("--work-dir", default=".smartedu-resources-work/textbooks", help="SmartEdu 教材内部索引工作目录")
    textbooks.add_argument("--sync", action="store_true", help="强制重新同步教材内部索引")
    textbooks.add_argument("-o", "--output", help="写入 JSON 文件")
    textbooks.set_defaults(func=run_textbook_candidates)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
