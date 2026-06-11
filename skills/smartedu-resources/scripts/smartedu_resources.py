#!/usr/bin/env python3
"""Normalize SmartEdu platform resources into learning resource candidates."""

from __future__ import annotations

import argparse
import html
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


def load_local_env() -> None:
    roots = [Path.cwd(), Path(__file__).resolve().parents[3]]
    seen: set[Path] = set()
    for root in roots:
        env_file = root / ".env.local"
        if env_file in seen or not env_file.exists():
            continue
        seen.add(env_file)
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env()


LIBRARY_LIST_URL = "https://api.ykt.cbern.com.cn/zxx/api_static/data/6_6_6/librarylist.json"
SEARCH_URLS = (
    "https://x-search.ykt.eduyun.cn/v1/resources/combine/search",
    "https://resource-gateway.ykt.eduyun.cn/resources/combine/search",
    "https://resource-gateway.ykt.eduyun.cn/resources/aggregate",
)
DETAIL_URLS = (
    "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{catalog}/details/{id}.json",
    "https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/resources/{catalog}/details/{id}.json",
)
DETAIL_ENDPOINT_FAMILY = "s-file-ndrv2-details"
SMARTEDU_FILE_SERVERS = ("s-file-1", "s-file-2", "s-file-3")
DETAIL_PAGE = (
    "https://basic.smartedu.cn/{catalog}/detail?"
    "contentType={content_type}&contentId={id}&catalogType={catalog}&subCatalog={sub_catalog}"
)
PRIVATE_HOST = "https://r1-ndr-private.ykt.cbern.com.cn"
DEFAULT_SDP_APP_ID = "e5649925-441d-4a53-b525-51a2f1c4e0a8"
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
DEFAULT_RESOURCE_TYPES = ["教材", "课程", "课件", "习题", "试卷", "视频", "音频", "图片", "文档", "实验", "专题", "家庭教育", "德育", "课后服务"]
DEFAULT_FORMATS = ["pdf", "doc", "docx", "ppt", "pptx", "jpg", "png", "mp3", "mp4", "m3u8", "zip", "网页"]
DEFAULT_TAB_CODES = [
    "sedu",
    "qualityCourse",
    "prepareLesson",
    "lecturer",
    "questions",
    "examinationPapers",
    "teachingKnMicroLesson",
    "listening",
    "singing",
    "sport",
    "art",
    "labourEdu",
    "schoolService",
    "childhoodEdu",
    "childhood_policy",
    "childhood_typexp",
    "childhood_care",
    "childhood_activities",
    "specialEdu",
    "family",
    "tchMaterial",
    "AIEducation",
    "technologyEdu",
    "areaSite",
    "studio-inst",
    "studio-inst-article",
    "studio-inst-res",
    "studio-inst-teachres",
    "studio-inst-spres",
    "studio-inst-exrc",
    "topic",
    "live",
    "school-space",
    "school-space-article",
    "school-space-res",
    "questions_ai_answer",
]
RESOURCE_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "json", "srt", "superboard", "jpg", "jpeg", "png", "webp", "gif", "mp3", "wav", "m4a", "mp4", "mov", "m3u8", "zip", "rar", "7z"}
SMARTEDU_API_TERMS = ["api", "resources", "resource", "librarylist", "details", "search", "aggregate", "combine", "ndrv2", "catalog", "course", "lesson", "content"]
CATALOG_TAB_HINTS = {
    "qualityCourse": "qualityCourse",
    "prepare_lesson": "prepareLesson",
    "prepareLesson": "prepareLesson",
    "questions": "questions",
    "question": "questions",
    "examinationPapers": "examinationPapers",
    "teachingKnMicroLesson": "teachingKnMicroLesson",
    "experiment": "experiment",
    "syncClassroom": "qualityCourse",
}


def norm(value: Any) -> str:
    return str(value or "").strip()


def clean_html_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return norm(re.sub(r"\s+", " ", text))


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
    extra_headers = extra_headers or {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://basic.smartedu.cn",
        "Referer": "https://basic.smartedu.cn/",
        "sdp-app-id": os.environ.get("SMARTEDU_SDP_APP_ID", DEFAULT_SDP_APP_ID),
    }
    authorization = os.environ.get("SMARTEDU_AUTHORIZATION")
    cookie = cookie or os.environ.get("SMARTEDU_COOKIE")
    if authorization:
        headers["Authorization"] = authorization
    if cookie:
        headers["Cookie"] = cookie
    headers.update(extra_headers)
    headers["Content-Type"] = "application/json;charset=UTF-8"
    return headers


def has_auth_context(access_token: str | None, cookie: str | None, extra_headers: dict[str, str]) -> bool:
    return bool(
        access_token
        or cookie
        or extra_headers
        or os.environ.get("SMARTEDU_COOKIE")
        or os.environ.get("SMARTEDU_AUTHORIZATION")
    )


def has_runtime_auth_context(access_token: str | None, cookie: str | None, extra_headers: dict[str, str], args: argparse.Namespace) -> bool:
    return has_auth_context(access_token, cookie, extra_headers) or bool(getattr(args, "browser_state", None))


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


def request_json_status(
    url: str,
    access_token: str | None = None,
    timeout: int = 20,
    payload: Any = None,
    cookie: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, int | None, str, str]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=build_headers(access_token, cookie=cookie, extra_headers=extra_headers))
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                return None, response.status, content_type, f"json decode failed: {exc}"
            return parsed if isinstance(parsed, dict) else {"data": parsed}, response.status, content_type, ""
    except HTTPError as exc:
        return None, exc.code, exc.headers.get("Content-Type", ""), str(exc)
    except (URLError, TimeoutError) as exc:
        return None, None, "", str(exc)


def browser_request_json_status(url: str, browser_state: str, timeout: int = 20) -> tuple[dict[str, Any] | None, int | None, str, str]:
    if not browser_state:
        return None, None, "", "missing browser state"
    state_file = Path(browser_state)
    if not state_file.exists():
        return None, None, "", f"missing browser state: {state_file}"
    script = Path(__file__).with_name("smartedu_browser_session.py")
    command = [
        sys.executable,
        str(script),
        "request",
        "--state-json",
        str(state_file),
        "--url",
        url,
        "--include-json",
        "--timeout",
        str(timeout),
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    output = completed.stdout.strip()
    if not output:
        return None, None, "", completed.stderr.strip() or f"browser request failed: exit {completed.returncode}"
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return None, None, "", f"browser request output decode failed: {exc}"
    response = data.get("response") if isinstance(data, dict) else {}
    if not isinstance(response, dict):
        return None, None, "", "browser request response missing"
    detail = response.get("json") if isinstance(response.get("json"), dict) else None
    status = response.get("status") if isinstance(response.get("status"), int) else None
    content_type = norm(response.get("content_type"))
    error = norm(response.get("error")) or (completed.stderr.strip() if completed.returncode not in {0, 1} else "")
    return detail, status, content_type, error


def request_text(
    url: str,
    access_token: str | None = None,
    timeout: int = 20,
    cookie: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    request = Request(url, headers=build_headers(access_token, cookie=cookie, extra_headers=extra_headers))
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def absolute_url(base_url: str, url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(url))


def resource_extension(url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    return "jpg" if suffix == "jpeg" else suffix


def safe_detail_page(detail: dict[str, Any], catalog: str, sub_catalog: str) -> str:
    resource_id = norm(detail.get("id"))
    content_type = norm(detail.get("resource_type_code")) or "resource"
    if catalog == "syncClassroom" and content_type == "national_lesson":
        return f"https://basic.smartedu.cn/syncClassroom/classActivity?activityId={urllib.parse.quote(resource_id)}"
    if catalog == "qualityCourse" and content_type == "elite_lesson":
        return f"https://basic.smartedu.cn/qualityCourse?courseId={urllib.parse.quote(resource_id)}"
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
    if fmt in {"srt", "vtt"}:
        return "字幕"
    if fmt == "json":
        return "数据"
    if fmt == "superboard":
        return "白板"
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
    return tab_codes or DEFAULT_TAB_CODES


def search_payload(args: argparse.Namespace, filters: dict[str, Any]) -> dict[str, Any]:
    query = args.query or norm(filters.get("query") or filters.get("core_topic") or filters.get("subject"))
    # 把 intent / task-json 的结构化字段映射为 SmartEdu tag 维度筛选
    tag_dimension_map = {
        "version": "tag.zxxbb",
        "grade": "tag.zxxnj",
        "volume": "tag.zxxcc",
        "subject": "tag.zxxxk",
        "stage": "tag.zxxxd",
    }
    combine_resources: list[dict[str, str]] = []
    for field, tag_field in tag_dimension_map.items():
        value = norm(filters.get(field))
        if value:
            # 年级数字转中文：1 -> 一年级, 3 -> 三年级
            value = grade_to_chinese(value)
            combine_resources.append({"field": tag_field, "value": value})
    return {
        "identity": args.identity,
        "identity_code": args.identity_code,
        "keyword": query,
        "tab_codes": parse_tab_codes(args.tab_code),
        "cross_tenant": args.cross_tenant,
        "duplicate_filter": True,
        "search_order": {"field": args.order_field, "direction": args.order_direction},
        "offset": args.offset,
        "limit": args.limit,
        "combine_intentions": [],
        "combine_resources": combine_resources,
    }


def grade_to_chinese(value: str) -> str:
    """将年级数字转为中文格式：'1' -> '一年级', '3' -> '三年级'。已是中文则原样返回。"""
    cn_digits = "零一二三四五六七八九十"
    m = re.match(r"^(\d+)$", value)
    if m:
        n = int(m.group(1))
        if 0 <= n <= 12:
            return cn_digits[n] + "年级"
    return value


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
    if not has_id:
        has_id = bool(identity_from_detail_page_url(detail_page_from_search_item(item)).get("resource_id"))
    has_title = any(item.get(key) for key in ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"])
    has_type = any(item.get(key) for key in ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "resource_type", "resourceType", "content_type", "contentType"])
    return bool(has_id and (has_title or has_type))


def extract_search_items(data: Any, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [item for group in candidate_lists(data) for item in group]:
        if not is_search_item_like(row):
            continue
        key = norm(first_value(row, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])) or identity_from_detail_page_url(detail_page_from_search_item(row)).get("resource_id", "")
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
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    fmt = norm(
        first_value(item, ["format", "file_format", "fileFormat", "resource_format", "resourceFormat", "ti_format"])
        or extra.get("format")
    ).lower()
    if "/" in fmt:
        fmt = fmt.rsplit("/", 1)[-1]
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    title_suffix = Path(clean_html_text(first_value(item, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"]))).suffix.lower().lstrip(".")
    detected = ("jpg" if fmt == "jpeg" else fmt) or suffix or title_suffix
    return detected if detected in RESOURCE_EXTENSIONS else "网页"


def search_tags_by_dimension(item: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for tag in item.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        dim = TAG_DIMENSIONS.get(str(tag.get("dimension_id") or tag.get("tag_dimension_id")))
        if dim and dim not in values:
            values[dim] = clean_html_text(tag.get("title") or tag.get("tag_name"))
    return values


def filter_search_items_by_tags(items: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """对搜索结果按 tags 做软过滤，保留相关性更高的条目。

    策略：
    - 版本（version）做硬过滤：用户指定"人教版"但条目标记"北师大版"则丢弃。
    - 年级和册次做软过滤（排序优先），不硬丢弃：因为同一单元可能在不同年级/册次
      有同名课程，且搜索关键词可能跨版本匹配。
    - 没有 tag 信息的条目保留。

    当版本硬过滤导致结果清空时，回退到不过滤版本，由 ranker 处理。
    """
    filter_fields = {
        "version": filters.get("version"),
        "grade": filters.get("grade"),
        "volume": filters.get("volume"),
        "stage": filters.get("stage"),
    }
    active_filters = {k: grade_to_chinese(norm(v)) for k, v in filter_fields.items() if v}
    if not active_filters:
        return items

    kept: list[dict[str, Any]] = []
    for item in items:
        tags = search_tags_by_dimension(item)
        drop = False
        for field, expected in active_filters.items():
            actual = norm(tags.get(field))
            if not actual:
                # 条目没有该维度 tag，保留
                continue
            if not tag_value_matches(actual, expected):
                # 只有 version 不匹配时硬过滤，其他维度软过滤（保留）
                if field == "version":
                    drop = True
                    break
                # grade/volume/stage 不匹配时保留，但不算精确匹配
        if not drop:
            kept.append(item)

    # 版本硬过滤导致结果清空时，回退到不做版本过滤，让 ranker 处理
    if not kept and "version" in active_filters and items:
        version_value = active_filters["version"]
        for item in items:
            tags = search_tags_by_dimension(item)
            actual = norm(tags.get("version"))
            if not actual or tag_value_matches(actual, version_value):
                kept.append(item)
        # 如果去掉版本过滤还是空，保留全部原始结果
        if not kept:
            kept = list(items)

    return kept


def tag_value_matches(actual: str, expected: str) -> bool:
    """宽松匹配 tag 值，处理常见变体如"一年级"/"1年级"/"一年级上"等。"""
    if actual == expected:
        return True
    # 数字与中文数字互转
    cn_digits = "零一二三四五六七八九十"
    def normalize_grade(s: str) -> str:
        s = norm(s)
        # "1年级" -> "一年级"
        m = re.match(r"(\d+)\s*年级", s)
        if m and int(m.group(1)) <= 12:
            return cn_digits[int(m.group(1))] + "年级"
        return s
    if normalize_grade(actual) == normalize_grade(expected):
        return True
    # 子串包含："上册" 匹配 "一年级上册" 中的册次
    if expected in actual or actual in expected:
        return True
    return False


def search_provider_name(item: dict[str, Any]) -> str:
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    providers = extra.get("providers") if isinstance(extra.get("providers"), list) else []
    names = [clean_html_text(row.get("name")) for row in providers if isinstance(row, dict) and clean_html_text(row.get("name"))]
    return "/".join(names) if names else ""


def detail_page_from_search_item(item: dict[str, Any]) -> str:
    explicit = norm(first_value(item, ["url", "web_url", "webUrl", "href", "detail_url", "detailUrl", "share_url", "shareUrl"]))
    if explicit.startswith("http"):
        return explicit
    resource_id = norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"]))
    catalog = norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"])) or "syncClassroom"
    sub_catalog = norm(first_value(item, ["sub_catalog", "subCatalog", "sub_catalog_code", "subCatalogCode"]))
    content_type = norm(first_value(item, ["content_type", "contentType", "resource_type", "resourceType", "resource_type_code", "resourceTypeCode"])) or "resource"
    if content_type == "national_lesson":
        return f"https://basic.smartedu.cn/syncClassroom/classActivity?activityId={urllib.parse.quote(resource_id)}"
    if content_type == "elite_lesson":
        return f"https://basic.smartedu.cn/qualityCourse?courseId={urllib.parse.quote(resource_id)}"
    if content_type == "prepare_lesson":
        return f"https://basic.smartedu.cn/syncClassroom/prepare/detail?resourceId={urllib.parse.quote(resource_id)}"
    return DETAIL_PAGE.format(
        catalog=urllib.parse.quote(catalog),
        content_type=urllib.parse.quote(content_type),
        id=urllib.parse.quote(resource_id),
        sub_catalog=urllib.parse.quote(sub_catalog),
    )


def explicit_detail_json_urls(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def walk(node: Any, key_hint: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, key)
        elif isinstance(node, list):
            for value in node:
                walk(value, key_hint)
        elif isinstance(node, str):
            value = html.unescape(node.strip())
            if not value.startswith(("http://", "https://")):
                return
            lowered_key = key_hint.lower()
            lowered_value = value.lower()
            if (("detail" in lowered_key or "json" in lowered_key) and ".json" in lowered_value) or "/details/" in lowered_value:
                urls.append(value)

    walk(item)
    return list(dict.fromkeys(urls))


def identity_from_detail_page_url(url: str) -> dict[str, str]:
    if not url.startswith(("http://", "https://")):
        return {}
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)

    def query_value(*names: str) -> str:
        for name in names:
            values = query.get(name)
            if values:
                return norm(values[0])
        return ""

    path_parts = [part for part in parsed.path.split("/") if part]
    catalog_from_path = path_parts[0] if path_parts else ""
    page_type = path_parts[1] if len(path_parts) > 1 else ""
    resource_id = query_value("contentId", "content_id", "resourceId", "resource_id", "activityId", "activity_id", "courseId", "course_id", "id")
    content_type = query_value("contentType", "content_type", "resourceType", "resource_type")
    if catalog_from_path == "syncClassroom" and page_type == "classActivity" and not content_type:
        content_type = "national_lesson"
    if catalog_from_path == "qualityCourse" and not content_type:
        content_type = "elite_lesson"
    return {
        "resource_id": resource_id,
        "tab_code": query_value("tabCode", "tab_code", "catalogType", "catalog") or catalog_from_path,
        "catalog": query_value("catalogType", "catalog") or catalog_from_path,
        "sub_catalog": query_value("subCatalog", "sub_catalog"),
        "content_type": content_type,
    }


def search_item_to_candidate(item: dict[str, Any], query: str, filters: dict[str, Any]) -> dict[str, Any]:
    source_url = detail_page_from_search_item(item)
    fmt = infer_format_from_item(item, source_url)
    title = clean_html_text(first_value(item, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"])) or "SmartEdu 资源"
    catalog = norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"]))
    resource_id = norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])) or stable_id(title + source_url)
    tag_values = search_tags_by_dimension(item)
    candidate = {
        "source": "smartedu-resources",
        "source_name": "国家中小学智慧教育平台",
        "source_url": source_url,
        "resource_id": f"smartedu-search:{resource_id}",
        "title": title,
        "description": clean_html_text(first_value(item, ["description", "summary", "intro", "content", "snippet", "global_description"])),
        "resource_type": norm(first_value(item, ["resource_type_name", "resourceTypeName", "content_type_name", "contentTypeName"])) or resource_type_for(fmt, {}, item),
        "format": fmt,
        "stage": norm(first_value(item, ["stage", "phase", "school_section"])) or tag_values.get("stage") or filters.get("stage"),
        "grade": norm(first_value(item, ["grade", "grade_name", "gradeName"])) or tag_values.get("grade") or filters.get("grade"),
        "subject": norm(first_value(item, ["subject", "subject_name", "subjectName"])) or tag_values.get("subject") or filters.get("subject"),
        "learning_domain": norm(first_value(item, ["subject", "subject_name", "subjectName"])) or tag_values.get("subject") or filters.get("learning_domain") or filters.get("subject"),
        "version": norm(first_value(item, ["version", "version_name", "versionName"])) or tag_values.get("version") or filters.get("version"),
        "volume": norm(first_value(item, ["volume", "book", "book_name", "bookName"])) or tag_values.get("volume") or filters.get("volume"),
        "topic": filters.get("core_topic") or query,
        "provider": norm(first_value(item, ["provider", "provider_name", "providerName", "source_name", "sourceName"])) or search_provider_name(item) or "国家中小学智慧教育平台",
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
    page_identity = identity_from_detail_page_url(detail_page_from_search_item(item))
    catalog = norm(first_value(item, ["catalog", "catalog_type", "catalogType", "tab_code", "tabCode", "channel_code", "channelCode"])) or page_identity.get("catalog") or "syncClassroom"
    resource_type = norm(first_value(item, ["resource_type", "resourceType", "resource_type_code", "resourceTypeCode", "content_type", "contentType"]))
    content_type = norm(first_value(item, ["content_type", "contentType"])) or resource_type or page_identity.get("content_type", "")
    if resource_type == "national_lesson":
        catalog = "syncClassroom"
        content_type = "national_lesson"
    elif resource_type == "elite_lesson":
        catalog = "qualityCourse"
        content_type = "elite_lesson"
    elif resource_type == "prepare_lesson":
        catalog = "prepareLesson"
        content_type = "prepare_lesson"
    return {
        "resource_id": norm(first_value(item, ["id", "resource_id", "resourceId", "content_id", "contentId", "course_id", "courseId"])) or page_identity.get("resource_id", ""),
        "tab_code": norm(first_value(item, ["tab_code", "tabCode", "channel_code", "channelCode"])) or page_identity.get("tab_code", "") or catalog,
        "catalog": catalog,
        "sub_catalog": norm(first_value(item, ["sub_catalog", "subCatalog", "sub_catalog_code", "subCatalogCode"])) or page_identity.get("sub_catalog", ""),
        "content_type": content_type,
        "resource_type": resource_type,
        "resource_type_name": clean_html_text(first_value(item, ["resource_type_name", "resourceTypeName", "content_type_name", "contentTypeName"])),
    }


def detail_urls_for_identity(identity: dict[str, str]) -> list[dict[str, str]]:
    resource_id = identity.get("resource_id") or ""
    catalog = identity.get("catalog") or "syncClassroom"
    tab_code = identity.get("tab_code") or catalog
    content_type = identity.get("content_type") or identity.get("resource_type") or ""
    if not resource_id:
        return []
    urls: list[dict[str, str]] = []
    special_templates: list[tuple[str, str]] = []
    if catalog == "syncClassroom" or tab_code in {"syncClassroom", "classActivity"} or content_type == "national_lesson":
        special_templates.append(("s-file-ndrv2-national-lesson-detail", "https://{server}.ykt.cbern.com.cn/zxx/ndrv2/national_lesson/resources/details/{id}.json"))
    if catalog in {"prepareLesson", "prepare_lesson"} or tab_code in {"prepareLesson", "prepare_lesson"} or content_type == "prepare_lesson":
        special_templates.append(("s-file-ndrv2-prepare-sub-type-detail", "https://{server}.ykt.cbern.com.cn/zxx/ndrv2/prepare_sub_type/resources/details/{id}.json"))
    if catalog == "qualityCourse" or tab_code == "qualityCourse" or content_type == "elite_lesson":
        special_templates.append(("s-file-ndrv2-quality-course-detail", "https://{server}.ykt.cbern.com.cn/zxx/ndrv2/resources/{id}.json"))
    if catalog == "tchMaterial" or tab_code == "tchMaterial":
        special_templates.append(("s-file-ndrv2-tch-material-detail", "https://{server}.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{id}.json"))

    seen: set[str] = set()
    for family, template in special_templates:
        for index, server in enumerate(SMARTEDU_FILE_SERVERS, 1):
            url = template.format(server=server, id=urllib.parse.quote(resource_id))
            if url in seen:
                continue
            seen.add(url)
            urls.append(
                {
                    "url": url,
                    "endpoint_family": family,
                    "template_index": f"special-{index}",
                }
            )
    for index, template in enumerate(DETAIL_URLS, 1):
        url = template.format(catalog=urllib.parse.quote(catalog), id=urllib.parse.quote(resource_id))
        if url in seen:
            continue
        seen.add(url)
        urls.append(
            {
                "url": url,
                "endpoint_family": DETAIL_ENDPOINT_FAMILY,
                "template_index": str(index),
            }
        )
    return urls


def values_from_candidates(candidates: list[dict[str, Any]], field: str) -> list[str]:
    return [norm(candidate.get(field)) for candidate in candidates if norm(candidate.get(field))]


def search_model_context(items: list[dict[str, Any]], candidates: list[dict[str, Any]], query: str, filters: dict[str, Any]) -> dict[str, Any]:
    dimensions = {
        "stage": count_values(values_from_candidates(candidates, "stage")),
        "grade": count_values(values_from_candidates(candidates, "grade")),
        "subject": count_values(values_from_candidates(candidates, "subject")),
        "version": count_values(values_from_candidates(candidates, "version")),
        "volume": count_values(values_from_candidates(candidates, "volume")),
        "resource_type": count_values(values_from_candidates(candidates, "resource_type")),
        "format": count_values(values_from_candidates(candidates, "format")),
        "provider": count_values(values_from_candidates(candidates, "provider")),
    }
    ambiguity: list[dict[str, Any]] = []
    for field in ["grade", "subject", "version", "volume", "resource_type", "provider"]:
        values = dimensions.get(field) or {}
        specified = norm(filters.get(field))
        if len(values) > 1 and not specified:
            ambiguity.append({"field": field, "values": values})

    detail_options: list[dict[str, Any]] = []
    for index, item in enumerate(items[:12], 1):
        identity = search_item_identity(item)
        detail_url = detail_page_from_search_item(item)
        title = clean_html_text(first_value(item, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"])) or "SmartEdu 资源"
        tag_values = search_tags_by_dimension(item)
        detail_options.append(
            {
                "rank": index,
                "title": title,
                "detail_page": detail_url,
                "resource_id": identity.get("resource_id"),
                "tab_code": identity.get("tab_code"),
                "catalog": identity.get("catalog"),
                "content_type": identity.get("content_type"),
                "resource_type": identity.get("resource_type") or identity.get("resource_type_name"),
                "stage": tag_values.get("stage"),
                "grade": tag_values.get("grade"),
                "subject": tag_values.get("subject"),
                "version": tag_values.get("version"),
                "volume": tag_values.get("volume"),
                "provider": search_provider_name(item),
                "next_command": f"candidates-from-detail --url {json.dumps(detail_url, ensure_ascii=False)}",
            }
        )

    return {
        "purpose": "给模型做需求澄清、范围判断和下一步工具调用决策；脚本不替模型硬编码上册/下册/版本选择。",
        "query": query,
        "detected_dimensions": dimensions,
        "ambiguity": ambiguity,
        "coverage_hint": "用户表达全部/整套/完整覆盖时，模型应按课程包、资源类型、主题范围和来源维度聚合；测试取样时可选择最相关详情页。",
        "detail_options": detail_options,
        "suggested_model_actions": [
            "需求范围不明确时优先追问学习主题、资源类型、使用场景或覆盖范围",
            "只有用户明确要求指定教材或唯一定位资源时，才追问版本、出版社或册次",
            "用户要求完整覆盖时不要只取第一条，应按课程包、resource_type、主题范围和来源分组后批量展开详情",
            "测试取样时可选 detail_options[0] 继续 candidates-from-detail",
        ],
    }


def detail_url_attempts_for_search_item(item: dict[str, Any], identity: dict[str, str]) -> list[dict[str, str]]:
    attempts: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, url in enumerate(explicit_detail_json_urls(item), 1):
        if url in seen:
            continue
        seen.add(url)
        attempts.append(
            {
                "url": url,
                "endpoint_family": "search-item-detail-json",
                "template_index": f"explicit-{index}",
            }
        )
    for attempt in detail_urls_for_identity(identity):
        url = attempt["url"]
        if url in seen:
            continue
        seen.add(url)
        attempts.append(attempt)
    return attempts


def classify_detail_probe(
    status: int | None,
    detail: dict[str, Any] | None,
    error: str,
    offline: bool = False,
) -> str:
    if offline and detail is None:
        return "detail_not_found_in_dir"
    if detail is not None:
        items = detail.get("ti_items")
        if isinstance(items, list) and items:
            return "ok_with_file_items"
        return "ok_no_file_items"
    if status == 403:
        return "requires_auth"
    if status == 404:
        return "not_found"
    if status is None:
        return "request_failed"
    if error:
        return "invalid_json" if "json decode failed" in error else "request_failed"
    return "unknown"


def detail_access_policy(status: str, via_browser: bool = False) -> str:
    if status in {"ok_with_file_items", "ok_no_file_items"}:
        if via_browser:
            return "browser_session_detail"
        return "public_detail"
    if status == "requires_auth":
        return "requires_auth_context"
    if status in {"detail_not_found_in_dir", "not_found"}:
        return "unavailable_or_template_unknown"
    return "runtime_validation_needed"


def detail_summary_for_probe(probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "detail_status": probe.get("detail_status") or "unknown",
        "detail_access_policy": probe.get("detail_access_policy") or "runtime_validation_needed",
        "detail_endpoint_family": probe.get("detail_endpoint_family") or DETAIL_ENDPOINT_FAMILY,
        "file_item_count": int(probe.get("file_item_count") or 0),
        "parsed_candidate_count": int(probe.get("parsed_candidate_count") or 0),
        "attempt_count": len(probe.get("attempts") or []),
        "error": probe.get("error") or "",
    }


def annotate_candidate_detail(candidate: dict[str, Any], detail_summary: dict[str, Any]) -> dict[str, Any]:
    raw = candidate.setdefault("raw", {})
    if isinstance(raw, dict):
        raw["smartedu_detail"] = detail_summary
    return candidate


def detail_failure_for_probe(probe: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    summary = detail_summary_for_probe(probe)
    return {
        "resource_id": identity.get("resource_id", ""),
        "catalog": identity.get("catalog", ""),
        "detail_status": summary["detail_status"],
        "detail_access_policy": summary["detail_access_policy"],
        "detail_endpoint_family": summary["detail_endpoint_family"],
        "file_item_count": summary["file_item_count"],
        "error": summary["error"] or summary["detail_status"],
    }


def detail_matrix_conclusion(status_counts: dict[str, int], access_policy_counts: dict[str, int]) -> str:
    if status_counts.get("ok_with_file_items", 0) > 0:
        return "公开可取"
    if status_counts.get("ok_no_file_items", 0) > 0:
        return "无文件项"
    if status_counts.get("requires_auth", 0) > 0 or access_policy_counts.get("requires_auth_context", 0) > 0:
        return "需要授权"
    if status_counts.get("detail_not_found_in_dir", 0) > 0 or status_counts.get("not_found", 0) > 0:
        return "模板未知"
    if status_counts.get("missing_resource_id", 0) > 0:
        return "模板未知"
    return "需运行时验证"


def detail_probe_matrix(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for probe in probes:
        tab_code = norm(probe.get("tab_code"))
        resource_type = norm(probe.get("resource_type"))
        resource_type_name = norm(probe.get("resource_type_name"))
        catalog = norm(probe.get("catalog"))
        sub_catalog = norm(probe.get("sub_catalog"))
        content_type = norm(probe.get("content_type"))
        key = "|".join([tab_code, resource_type, resource_type_name, catalog, sub_catalog, content_type])
        group = groups.setdefault(
            key,
            {
                "tab_code": tab_code,
                "resource_type": resource_type,
                "resource_type_name": resource_type_name,
                "catalog": catalog,
                "sub_catalog": sub_catalog,
                "content_type": content_type,
                "detail_endpoint_family": probe.get("detail_endpoint_family") or DETAIL_ENDPOINT_FAMILY,
                "detail_url_templates": probe.get("detail_url_templates") or [],
                "resource_ids": [],
                "probe_count": 0,
                "detail_status_values": [],
                "detail_access_policy_values": [],
                "file_item_count": 0,
                "parsed_candidate_count": 0,
            },
        )
        if probe.get("resource_id"):
            group["resource_ids"].append(probe.get("resource_id"))
        group["probe_count"] += 1
        group["detail_status_values"].append(norm(probe.get("detail_status")))
        group["detail_access_policy_values"].append(norm(probe.get("detail_access_policy")))
        group["file_item_count"] += int(probe.get("file_item_count") or 0)
        group["parsed_candidate_count"] += int(probe.get("parsed_candidate_count") or 0)
    matrix: list[dict[str, Any]] = []
    for group in groups.values():
        status_counts = count_values(group.pop("detail_status_values"))
        access_policy_counts = count_values(group.pop("detail_access_policy_values"))
        resource_ids = list(dict.fromkeys(group.pop("resource_ids")))
        group["search_items_seen"] = int(group.pop("probe_count") or 0)
        group["sample_resource_ids"] = resource_ids[:5]
        group["detail_status_counts"] = status_counts
        group["detail_access_policy_counts"] = access_policy_counts
        group["conclusion"] = detail_matrix_conclusion(status_counts, access_policy_counts)
        matrix.append(group)
    return sorted(matrix, key=lambda item: (item.get("tab_code") or "", item.get("resource_type") or "", item.get("content_type") or ""))


def probe_detail_for_search_item(
    item: dict[str, Any],
    args: argparse.Namespace,
    access_token: str | None,
    extra_headers: dict[str, str],
) -> dict[str, Any]:
    identity = search_item_identity(item)
    title = clean_html_text(first_value(item, ["title", "name", "content_name", "contentName", "resource_name", "resourceName", "global_title"]))
    result: dict[str, Any] = {
        "resource_id": identity.get("resource_id") or "",
        "title": title,
        "tab_code": identity.get("tab_code") or "",
        "catalog": identity.get("catalog") or "",
        "sub_catalog": identity.get("sub_catalog") or "",
        "content_type": identity.get("content_type") or "",
        "resource_type": identity.get("resource_type") or "",
        "resource_type_name": identity.get("resource_type_name") or "",
        "detail_page": detail_page_from_search_item(item),
        "detail_endpoint_family": DETAIL_ENDPOINT_FAMILY,
        "detail_url_templates": [attempt["url"] for attempt in detail_url_attempts_for_search_item(item, identity)],
        "detail_status": "missing_resource_id" if not identity.get("resource_id") else "not_attempted",
        "detail_access_policy": "template_unknown" if not identity.get("resource_id") else "runtime_validation_needed",
        "attempts": [],
        "file_item_count": 0,
        "parsed_candidate_count": 0,
        "error": "",
    }
    if not identity.get("resource_id"):
        result["error"] = "missing resource id"
        return result

    cached = load_detail_from_dir(args.detail_dir, identity)
    if cached is not None:
        candidates, seen, skipped = candidates_from_detail(cached, identity["catalog"], identity["sub_catalog"], {})
        status = classify_detail_probe(200, cached, "")
        result.update(
            {
                "detail_status": status,
                "detail_access_policy": detail_access_policy(status),
                "attempts": [
                    {
                        "source": "detail_dir",
                        "status": 200,
                        "content_type": "application/json",
                        "has_json": True,
                        "has_ti_items": isinstance(cached.get("ti_items"), list),
                        "ti_items": seen,
                        "skipped_items": skipped,
                        "error": "",
                    }
                ],
                "file_item_count": seen,
                "parsed_candidate_count": len(candidates),
            }
        )
        return result
    if args.offline_details_only:
        status = classify_detail_probe(None, None, "", offline=True)
        result.update({"detail_status": status, "detail_access_policy": detail_access_policy(status), "error": "detail not found in detail dir"})
        return result

    for attempt in detail_url_attempts_for_search_item(item, identity):
        detail, status_code, content_type, error = request_json_status(
            attempt["url"],
            access_token=access_token,
            timeout=args.timeout,
            cookie=args.cookie,
            extra_headers=extra_headers,
        )
        candidates: list[dict[str, Any]] = []
        seen = 0
        skipped = 0
        if detail is not None:
            candidates, seen, skipped = candidates_from_detail(detail, identity["catalog"], identity["sub_catalog"], {})
        classified = classify_detail_probe(status_code, detail, error)
        result["attempts"].append(
            {
                "url": attempt["url"],
                "endpoint_family": attempt["endpoint_family"],
                "template_index": attempt["template_index"],
                "status": status_code,
                "content_type": content_type,
                "has_json": detail is not None,
                "has_ti_items": bool(detail is not None and isinstance(detail.get("ti_items"), list)),
                "ti_items": seen,
                "skipped_items": skipped,
                "error": error,
                "classified_status": classified,
            }
        )
        if detail is not None:
            result.update(
                {
                    "detail_status": classified,
                    "detail_access_policy": detail_access_policy(classified),
                    "detail_endpoint_family": attempt["endpoint_family"],
                    "file_item_count": seen,
                    "parsed_candidate_count": len(candidates),
                    "error": error,
                }
            )
            break
        if getattr(args, "browser_state", None) and classified in {"requires_auth", "request_failed"}:
            browser_detail, browser_status, browser_content_type, browser_error = browser_request_json_status(attempt["url"], args.browser_state, timeout=args.timeout)
            browser_candidates: list[dict[str, Any]] = []
            browser_seen = 0
            browser_skipped = 0
            if browser_detail is not None:
                browser_candidates, browser_seen, browser_skipped = candidates_from_detail(browser_detail, identity["catalog"], identity["sub_catalog"], {})
            browser_classified = classify_detail_probe(browser_status, browser_detail, browser_error)
            result["attempts"].append(
                {
                    "source": "browser_state",
                    "url": attempt["url"],
                    "endpoint_family": attempt["endpoint_family"],
                    "template_index": attempt["template_index"],
                    "status": browser_status,
                    "content_type": browser_content_type,
                    "has_json": browser_detail is not None,
                    "has_ti_items": bool(browser_detail is not None and isinstance(browser_detail.get("ti_items"), list)),
                    "ti_items": browser_seen,
                    "skipped_items": browser_skipped,
                    "error": browser_error,
                    "classified_status": browser_classified,
                }
            )
            if browser_detail is not None:
                result.update(
                    {
                        "detail_status": browser_classified,
                        "detail_access_policy": detail_access_policy(browser_classified, via_browser=True),
                        "detail_endpoint_family": attempt["endpoint_family"],
                        "file_item_count": browser_seen,
                        "parsed_candidate_count": len(browser_candidates),
                        "error": browser_error,
                    }
                )
                break
        if status_code in {403, 404}:
            result.update(
                {
                    "detail_status": classified,
                    "detail_access_policy": detail_access_policy(classified),
                    "detail_endpoint_family": attempt["endpoint_family"],
                    "file_item_count": seen,
                    "parsed_candidate_count": len(candidates),
                    "error": error,
                }
            )
            if status_code == 404:
                break
    if result["detail_status"] == "not_attempted" and result["attempts"]:
        last = result["attempts"][-1]
        status = classify_detail_probe(last.get("status"), None, last.get("error") or "")
        result.update(
            {
                "detail_status": status,
                "detail_access_policy": detail_access_policy(status),
                "detail_endpoint_family": last.get("endpoint_family") or DETAIL_ENDPOINT_FAMILY,
                "error": last.get("error") or "",
            }
        )
    return result


def fetch_detail_for_search_item(
    item: dict[str, Any],
    identity: dict[str, str],
    args: argparse.Namespace,
    access_token: str | None,
    extra_headers: dict[str, str],
) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in detail_url_attempts_for_search_item(item, identity):
        detail, status_code, _content_type, error = request_json_status(
            attempt["url"],
            access_token=access_token,
            timeout=getattr(args, "timeout", 20),
            cookie=args.cookie,
            extra_headers=extra_headers,
        )
        if detail is not None:
            return detail
        errors.append(f"{attempt['url']}: status={status_code} error={error}")
        if getattr(args, "browser_state", None) and status_code in {None, 403}:
            browser_detail, browser_status, _browser_content_type, browser_error = browser_request_json_status(attempt["url"], args.browser_state, timeout=getattr(args, "timeout", 20))
            if browser_detail is not None:
                return browser_detail
            errors.append(f"browser_state {attempt['url']}: status={browser_status} error={browser_error}")
    raise RuntimeError("; ".join(errors) or "no detail urls to try")


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
) -> tuple[dict[str, Any] | None, dict[str, str], str | None, dict[str, Any]]:
    identity = search_item_identity(item)
    if not identity["resource_id"]:
        probe = probe_detail_for_search_item(item, args, access_token, extra_headers)
        return None, identity, "missing resource id", probe
    cached = load_detail_from_dir(args.detail_dir, identity)
    if cached is not None:
        probe = probe_detail_for_search_item(item, args, access_token, extra_headers)
        return cached, identity, None, probe
    if args.offline_details_only:
        probe = probe_detail_for_search_item(item, args, access_token, extra_headers)
        return None, identity, "detail not found in detail dir", probe
    probe = probe_detail_for_search_item(item, args, access_token, extra_headers)
    if probe.get("detail_status") in {"ok_with_file_items", "ok_no_file_items"}:
        cached_after_probe = load_detail_from_dir(args.detail_dir, identity)
        if cached_after_probe is not None:
            return cached_after_probe, identity, None, probe
    try:
        return (
            fetch_detail_for_search_item(item, identity, args, access_token, extra_headers),
            identity,
            None,
            probe,
        )
    except Exception as exc:
        if not probe.get("error"):
            probe["error"] = str(exc)
        return None, identity, str(exc), probe


def candidate_title(detail: dict[str, Any], item: dict[str, Any], fmt: str) -> str:
    title = norm(detail.get("title") or detail.get("global_title"))
    custom = detail.get("custom_properties") if isinstance(detail.get("custom_properties"), dict) else {}
    original_title = norm(custom.get("original_title") or custom.get("alias_name"))
    if original_title and original_title not in title:
        title = f"{title} - {original_title}" if title else original_title
    flag = norm(item.get("ti_file_flag"))
    if flag and flag not in {"source", "href", "href-m3u8"}:
        return f"{title} - {flag}"
    if fmt and fmt != "unknown":
        return f"{title} - {fmt.upper()}"
    return title or norm(detail.get("id")) or "SmartEdu 资源"


def relation_resource_details(detail: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    if isinstance(detail.get("ti_items"), list):
        resources.append(detail)

    relations = detail.get("relations") if isinstance(detail.get("relations"), dict) else {}
    relation_keys = [
        "national_course_resource",
        "course_resource",
        "resources",
        "resource",
    ]
    for key in relation_keys:
        rows = relations.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("ti_items"), list):
                continue
            merged = dict(detail)
            merged.update(row)
            if not merged.get("provider_list") and detail.get("provider_list"):
                merged["provider_list"] = detail.get("provider_list")
            if not merged.get("tag_list") and detail.get("tag_list"):
                merged["tag_list"] = detail.get("tag_list")
            resources.append(merged)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for resource in resources:
        key = norm(resource.get("id")) or stable_id(json.dumps(resource.get("ti_items") or [], ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        unique.append(resource)
    return unique


def candidates_from_detail(detail: dict[str, Any], catalog: str, sub_catalog: str, filters: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], int, int]:
    filters = filters or {}
    candidates: list[dict[str, Any]] = []
    skipped = 0
    total_items = 0
    for resource_detail in relation_resource_details(detail):
        dimensions = tags_by_dimension(resource_detail) or tags_by_dimension(detail)
        detail_page = safe_detail_page(resource_detail, catalog or norm(resource_detail.get("catalog")), sub_catalog)
        provider = provider_name(resource_detail)
        items = resource_detail.get("ti_items") or []
        total_items += len(items)
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
            if fmt in {"folder", "unknown"}:
                skipped += 1
                continue
            requires_auth = item_requires_auth(item, urls)
            warnings = ["可能需要 SmartEdu 登录授权"] if requires_auth else []
            resource_type = resource_type_for(fmt, item, resource_detail)
            smartedu_detail_id = norm(resource_detail.get("id") or detail.get("id"))
            candidate = {
                "source": "smartedu-resources",
                "source_name": "国家中小学智慧教育平台",
                "source_url": primary_url,
                "resource_id": f"{smartedu_detail_id}:{index}:{stable_id(primary_url)}",
                "title": candidate_title(resource_detail, item, fmt),
                "description": norm(resource_detail.get("description") or resource_detail.get("global_description") or detail.get("description") or detail.get("global_description")),
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
                "size": requirement_value(item, "FileSize") or requirement_value(item, "total_size") or item.get("ti_size"),
                "metadata_confidence": 0.0,
                "raw": {
                    "detail_page": detail_page,
                    "smartedu_detail_id": smartedu_detail_id,
                    "smartedu_catalog": catalog,
                    "smartedu_sub_catalog": sub_catalog,
                    "smartedu_item_index": index,
                    "smartedu_item": item,
                    "smartedu_resource_item": resource_detail,
                    "url_candidates": urls,
                    "warnings": warnings,
                },
            }
            candidate["metadata_confidence"] = metadata_confidence(candidate)
            candidates.append(candidate)
    return candidates, total_items, skipped


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


def catalog_summary(catalogs: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, int] = {}
    for item in catalogs:
        family = norm(item.get("resource_family")) or "通用资源"
        families[family] = families.get(family, 0) + 1
    return {
        "catalogs": len(catalogs),
        "resource_catalogs": sum(1 for item in catalogs if item.get("known_skill") == "smartedu-resources"),
        "external_catalogs": sum(1 for item in catalogs if item.get("external")),
        "textbook_catalogs": sum(1 for item in catalogs if item.get("internal_adapter") == "tchMaterial"),
        "resource_families": families,
    }


def catalog_page_url(row: dict[str, Any]) -> str:
    catalog = norm(row.get("catalog")) or "syncClassroom"
    sub_catalog = norm(row.get("sub_catalog"))
    if catalog == "tchMaterial":
        return "https://basic.smartedu.cn/tchMaterial"
    if sub_catalog:
        return f"https://basic.smartedu.cn/{urllib.parse.quote(catalog)}?subCatalog={urllib.parse.quote(sub_catalog)}"
    return f"https://basic.smartedu.cn/{urllib.parse.quote(catalog)}"


def search_tab_for(row: dict[str, Any]) -> str:
    row_type = norm(row.get("type"))
    catalog = norm(row.get("catalog"))
    sub_catalog = norm(row.get("sub_catalog"))
    for value in [row_type, sub_catalog, catalog]:
        if value in CATALOG_TAB_HINTS:
            return CATALOG_TAB_HINTS[value]
    return row_type or sub_catalog or catalog or DEFAULT_TAB_CODES[0]


def route_for_catalog(row: dict[str, Any]) -> dict[str, Any]:
    catalog = norm(row.get("catalog")) or "syncClassroom"
    sub_catalog = norm(row.get("sub_catalog"))
    row_type = norm(row.get("type"))
    internal_adapter = norm(row.get("internal_adapter"))
    if internal_adapter == "tchMaterial" or catalog == "tchMaterial" or row_type == "tchMaterial":
        scan_strategy = "internal_adapter"
        commands = [
            "textbook-candidates",
        ]
        endpoints = []
        detail_templates = []
    else:
        scan_strategy = "search_then_detail"
        commands = [
            "search-resources",
            "candidates-from-detail",
        ]
        endpoints = list(SEARCH_URLS)
        detail_templates = [template.format(catalog=catalog, id="{id}") for template in DETAIL_URLS]
    return {
        "route_id": stable_id("|".join([catalog, sub_catalog, row_type, norm(row.get("title"))])),
        "title": row.get("title"),
        "catalog": catalog,
        "catalog_name": row.get("catalog_name"),
        "sub_catalog": sub_catalog,
        "sub_catalog_name": row.get("sub_catalog_name"),
        "type": row_type,
        "resource_family": row.get("resource_family") or "通用资源",
        "page_url": catalog_page_url(row),
        "known_skill": "smartedu-resources",
        "internal_adapter": internal_adapter,
        "scan_strategy": scan_strategy,
        "supported_commands": commands,
        "search_tab_code": search_tab_for(row),
        "search_payload_defaults": {
            "origin": "basic",
            "resource_search_type": "resource",
            "tab_codes": [search_tab_for(row)],
            "catalog": catalog,
            "sub_catalog": sub_catalog,
        },
        "detail_url_templates": detail_templates,
        "requires_runtime_validation": scan_strategy != "internal_adapter",
        "notes": [
            "搜索接口返回候选后通常还需要详情 JSON 才能解析真实文件项。",
            "详情文件项解析依赖 ti_items。",
        ]
        if scan_strategy != "internal_adapter"
        else ["教材分支当前通过内部兼容适配器生成候选。"],
        "raw_catalog": row.get("raw") or {},
    }


def dedupe_routes(routes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0
    for route in routes:
        key = norm(route.get("route_id")) or stable_id(
            "|".join(
                [
                    norm(route.get("catalog")),
                    norm(route.get("sub_catalog")),
                    norm(route.get("type")),
                    norm(route.get("title")),
                ]
            )
        )
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(route)
    return unique, duplicates


def run_route_map(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    if args.library_list_json:
        data = load_json(args.library_list_json)
    else:
        data = request_json(LIBRARY_LIST_URL, access_token=access_token, cookie=args.cookie, extra_headers=extra_headers)
    if not isinstance(data, list):
        raise ValueError("library list must be a JSON list")
    catalogs = flatten_catalogs(data)
    routes, duplicates = dedupe_routes([route_for_catalog(row) for row in catalogs])
    result = {
        "route_map_schema": "smartedu-route-map/v1",
        "source_skill": "smartedu-resources",
        "mapped_at": datetime.now(timezone.utc).isoformat(),
        "routes": routes,
        "summary": {
            "routes": len(routes),
            "duplicates_removed": duplicates,
            "internal_adapter_routes": sum(1 for item in routes if item.get("scan_strategy") == "internal_adapter"),
            "search_then_detail_routes": sum(1 for item in routes if item.get("scan_strategy") == "search_then_detail"),
            "catalogs": catalog_summary(catalogs),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
        },
    }
    write_output(args.output, result)
    return 0


def routes_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.route_map_json:
        data = load_json(args.route_map_json)
        routes = data.get("routes") if isinstance(data, dict) else []
        if not isinstance(routes, list):
            raise ValueError("route-map JSON must contain routes list")
        return dedupe_routes([item for item in routes if isinstance(item, dict)])[0]
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    if args.library_list_json:
        data = load_json(args.library_list_json)
    else:
        data = request_json(LIBRARY_LIST_URL, access_token=access_token, cookie=args.cookie, extra_headers=extra_headers)
    if not isinstance(data, list):
        raise ValueError("library list must be a JSON list")
    return dedupe_routes([route_for_catalog(row) for row in flatten_catalogs(data)])[0]


def select_routes(routes: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for route in routes:
        if args.route_id and route.get("route_id") != args.route_id:
            continue
        if args.catalog and route.get("catalog") != args.catalog:
            continue
        if args.sub_catalog and route.get("sub_catalog") != args.sub_catalog:
            continue
        if args.type and route.get("type") != args.type:
            continue
        if args.title and args.title not in norm(route.get("title")):
            continue
        selected.append(route)
    if getattr(args, "all_routes", False) or args.route_limit <= 0:
        return selected
    return selected[: args.route_limit]


def count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = norm(value) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def route_coverage(routes: list[dict[str, Any]]) -> dict[str, Any]:
    command_values: list[str] = []
    for route in routes:
        command_values.extend(str(item) for item in route.get("supported_commands") or [])
    return {
        "catalogs": count_values([norm(item.get("catalog")) for item in routes]),
        "sub_catalogs": count_values([norm(item.get("sub_catalog")) for item in routes if norm(item.get("sub_catalog"))]),
        "types": count_values([norm(item.get("type")) for item in routes]),
        "resource_families": count_values([norm(item.get("resource_family")) for item in routes]),
        "scan_strategies": count_values([norm(item.get("scan_strategy")) for item in routes]),
        "search_tab_codes": count_values([norm(item.get("search_tab_code")) for item in routes]),
        "supported_commands": count_values(command_values),
    }


def route_scan_plan(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_id": route.get("route_id"),
        "title": route.get("title"),
        "catalog": route.get("catalog"),
        "sub_catalog": route.get("sub_catalog"),
        "type": route.get("type"),
        "page_url": route.get("page_url"),
        "scan_strategy": route.get("scan_strategy"),
        "search_tab_code": route.get("search_tab_code"),
        "supported_commands": route.get("supported_commands") or [],
        "requires_runtime_validation": bool(route.get("requires_runtime_validation")),
    }


def scan_route_summary(route_results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = count_values([norm(item.get("status")) for item in route_results])
    detail_status_values: list[str] = []
    detail_policy_values: list[str] = []
    for result in route_results:
        for candidate in result.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
            detail = raw.get("smartedu_detail") if isinstance(raw.get("smartedu_detail"), dict) else {}
            if detail:
                detail_status_values.append(norm(detail.get("detail_status")))
                detail_policy_values.append(norm(detail.get("detail_access_policy")))
        for failure in result.get("detail_failures") or []:
            if isinstance(failure, dict):
                detail_status_values.append(norm(failure.get("detail_status")))
                detail_policy_values.append(norm(failure.get("detail_access_policy")))
    return {
        "routes_scanned": len(route_results),
        "statuses": statuses,
        "search_items_seen": sum(int(item.get("search_items_seen") or 0) for item in route_results),
        "candidates": sum(len(item.get("candidates") or []) for item in route_results),
        "detail_failures": sum(len(item.get("detail_failures") or []) for item in route_results),
        "details_fetched": sum(int((item.get("summary") or {}).get("details_fetched") or 0) for item in route_results),
        "detail_items_seen": sum(int((item.get("summary") or {}).get("detail_items_seen") or 0) for item in route_results),
        "detail_status_counts": count_values(detail_status_values),
        "detail_access_policy_counts": count_values(detail_policy_values),
    }


def route_detail_coverage(route_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for result in route_results:
        route = result.get("route") if isinstance(result.get("route"), dict) else {}
        detail_status_values: list[str] = []
        detail_policy_values: list[str] = []
        for candidate in result.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
            detail = raw.get("smartedu_detail") if isinstance(raw.get("smartedu_detail"), dict) else {}
            if detail:
                detail_status_values.append(norm(detail.get("detail_status")))
                detail_policy_values.append(norm(detail.get("detail_access_policy")))
        for failure in result.get("detail_failures") or []:
            if isinstance(failure, dict):
                detail_status_values.append(norm(failure.get("detail_status")))
                detail_policy_values.append(norm(failure.get("detail_access_policy")))
        if not detail_status_values and not detail_policy_values:
            continue
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        coverage.append(
            {
                "route_id": route.get("route_id"),
                "title": route.get("title"),
                "catalog": route.get("catalog"),
                "sub_catalog": route.get("sub_catalog"),
                "type": route.get("type"),
                "search_tab_code": route.get("search_tab_code"),
                "search_items_seen": result.get("search_items_seen", 0),
                "details_fetched": int(summary.get("details_fetched") or 0),
                "detail_items_seen": int(summary.get("detail_items_seen") or 0),
                "detail_failures": len(result.get("detail_failures") or []),
                "detail_status_counts": count_values(detail_status_values),
                "detail_access_policy_counts": count_values(detail_policy_values),
            }
        )
    return coverage


def run_site_index(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    routes = select_routes(routes_from_args(args), args)
    if not routes:
        raise ValueError("no matching routes")

    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    scan_summary: dict[str, Any] = {}
    if args.site_scan_json:
        scan_data = load_json(args.site_scan_json)
        candidates = [item for item in scan_data.get("candidates") or [] if isinstance(item, dict)]
        failures = [item for item in scan_data.get("failures") or [] if isinstance(item, dict)]
        route_results = [item for item in scan_data.get("routes") or [] if isinstance(item, dict)]
        scan_summary = scan_data.get("summary") if isinstance(scan_data.get("summary"), dict) else {}
    detail_coverage = route_detail_coverage(route_results)

    output = {
        "site_index_schema": "smartedu-site-index/v1",
        "source_skill": "smartedu-resources",
        "source_name": "国家中小学智慧教育平台",
        "site_url": "https://basic.smartedu.cn/",
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "routes": routes,
        "scan_plan": [route_scan_plan(route) for route in routes],
        "coverage": route_coverage(routes),
        "candidates": candidates,
        "failures": failures,
        "scan_summary": scan_summary,
        "detail_coverage": detail_coverage,
        "summary": {
            "routes": len(routes),
            "search_then_detail_routes": sum(1 for item in routes if item.get("scan_strategy") == "search_then_detail"),
            "internal_adapter_routes": sum(1 for item in routes if item.get("scan_strategy") == "internal_adapter"),
            "runtime_validation_routes": sum(1 for item in routes if item.get("requires_runtime_validation")),
            "candidates": len(candidates),
            "failures": len(failures),
            "route_scan_summary": scan_route_summary(route_results) if route_results else {},
            "detail_coverage_routes": len(detail_coverage),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
        },
    }
    write_output(args.output, output)
    return 0


def scan_payload(query: str, route: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "identity": args.identity,
        "identity_code": args.identity_code,
        "keyword": query,
        "tab_codes": [route.get("search_tab_code") or DEFAULT_TAB_CODES[0]],
        "cross_tenant": args.cross_tenant,
        "duplicate_filter": True,
        "search_order": {"field": args.order_field, "direction": args.order_direction},
        "offset": args.offset,
        "limit": args.limit,
        "combine_intentions": [],
        "combine_resources": [],
    }


def scan_query(args: argparse.Namespace, route: dict[str, Any]) -> str:
    return args.query or norm(route.get("title") or route.get("catalog_name") or route.get("sub_catalog_name") or route.get("type"))


def scan_search_data(args: argparse.Namespace, route: dict[str, Any], access_token: str | None, extra_headers: dict[str, str]) -> tuple[Any, bool, str]:
    if args.search_response_json:
        return load_json(args.search_response_json), False, args.search_response_json
    payload = scan_payload(scan_query(args, route), route, args)
    if args.search_url:
        return request_json(args.search_url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers), True, args.search_url
    errors: list[str] = []
    for url in SEARCH_URLS:
        try:
            return request_json(url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers), True, url
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("; ".join(errors))


def route_scan_result(route: dict[str, Any], args: argparse.Namespace, access_token: str | None, extra_headers: dict[str, str]) -> dict[str, Any]:
    if route.get("scan_strategy") == "internal_adapter":
        return {
            "route": route,
            "status": "skipped_internal_adapter",
            "query": scan_query(args, route),
            "online": False,
            "endpoint": "",
            "search_items_seen": 0,
            "candidates": [],
            "detail_failures": [],
            "summary": {"note": "该栏目当前由内部适配器处理，请使用 textbook-candidates。"},
        }
    query = scan_query(args, route)
    data, online, endpoint = scan_search_data(args, route, access_token, extra_headers)
    items = extract_search_items(data, args.limit)
    scan_filters = load_task_filters(getattr(args, "task_json", None))
    items = filter_search_items_by_tags(items, scan_filters)
    candidates: list[dict[str, Any]] = []
    detail_failures: list[dict[str, str]] = []
    detail_items_seen = 0
    detail_items_skipped = 0
    details_fetched = 0
    if args.fetch_details:
        for item in items:
            detail, identity, error, probe = detail_for_search_item(item, args, access_token, extra_headers)
            detail_summary = detail_summary_for_probe(probe)
            if detail is None:
                fallback = search_item_to_candidate(item, query, {})
                fallback.setdefault("raw", {}).setdefault("warnings", []).append(f"详情追踪失败：{error or 'unknown error'}")
                annotate_candidate_detail(fallback, detail_summary)
                candidates.append(fallback)
                detail_failures.append(detail_failure_for_probe(probe, identity))
                continue
            detail_candidates, seen, skipped = candidates_from_detail(detail, identity["catalog"], identity["sub_catalog"], {})
            if detail_candidates:
                candidates.extend(annotate_candidate_detail(candidate, detail_summary) for candidate in detail_candidates)
            else:
                fallback = search_item_to_candidate(item, query, {})
                fallback.setdefault("raw", {}).setdefault("warnings", []).append("详情已获取但未解析出文件项")
                candidates.append(annotate_candidate_detail(fallback, detail_summary))
            details_fetched += 1
            detail_items_seen += seen
            detail_items_skipped += skipped
    else:
        candidates = [search_item_to_candidate(item, query, {}) for item in items]
    for candidate in candidates:
        raw = candidate.setdefault("raw", {})
        if isinstance(raw, dict):
            raw["smartedu_route_id"] = route.get("route_id")
            raw["smartedu_route_title"] = route.get("title")
            raw["smartedu_scan_strategy"] = route.get("scan_strategy")
    return {
        "route": route,
        "status": "ok" if candidates else "no_candidates",
        "query": query,
        "online": online,
        "endpoint": endpoint,
        "search_items_seen": len(items),
        "candidates": candidates,
        "detail_failures": detail_failures,
        "summary": {
            "candidates": len(candidates),
            "fetch_details": bool(args.fetch_details),
            "details_fetched": details_fetched,
            "detail_items_seen": detail_items_seen,
            "detail_items_skipped": detail_items_skipped,
            "detail_failures": len(detail_failures),
        },
    }


def run_scan_catalog(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    routes = select_routes(routes_from_args(args), args)
    if not routes:
        raise ValueError("no matching routes")
    route_results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for route in routes:
        result = route_scan_result(route, args, access_token, extra_headers)
        route_results.append(result)
        candidates.extend(item for item in result.get("candidates") or [] if isinstance(item, dict))
    output = {
        "scan_schema": "smartedu-catalog-scan/v1",
        "source_skill": "smartedu-resources",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "query": args.query or "",
        "routes": route_results,
        "candidates": candidates,
        "summary": {
            "routes_selected": len(routes),
            "routes_scanned": len(route_results),
            "candidates": len(candidates),
            "search_items_seen": sum(int(item.get("search_items_seen") or 0) for item in route_results),
            "route_scan_summary": scan_route_summary(route_results),
            "online": not bool(args.search_response_json),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
        },
    }
    write_output(args.output, output)
    return 0 if candidates else 1


def candidate_key(candidate: dict[str, Any]) -> str:
    return norm(candidate.get("source_url")) or norm(candidate.get("resource_id")) or stable_id(json.dumps(candidate, ensure_ascii=False, sort_keys=True))


def dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0
    for candidate in candidates:
        key = candidate_key(candidate)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(candidate)
    return unique, duplicates


def run_scan_site(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    routes = select_routes(routes_from_args(args), args)
    if not routes:
        raise ValueError("no matching routes")

    route_results: list[dict[str, Any]] = []
    raw_candidates: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    skipped_internal = 0
    for route in routes:
        try:
            result = route_scan_result(route, args, access_token, extra_headers)
            route_results.append(result)
            if result.get("status") == "skipped_internal_adapter":
                skipped_internal += 1
            raw_candidates.extend(item for item in result.get("candidates") or [] if isinstance(item, dict))
        except Exception as exc:
            failures.append(
                {
                    "route_id": norm(route.get("route_id")),
                    "title": norm(route.get("title")),
                    "catalog": norm(route.get("catalog")),
                    "error": str(exc),
                }
            )
            if not args.continue_on_error:
                break
    candidates, duplicates = dedupe_candidates(raw_candidates)
    output = {
        "site_scan_schema": "smartedu-site-scan/v1",
        "source_skill": "smartedu-resources",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "query": args.query or "",
        "routes": route_results,
        "candidates": candidates,
        "failures": failures,
        "summary": {
            "routes_selected": len(routes),
            "routes_scanned": len(route_results),
            "routes_failed": len(failures),
            "internal_adapter_routes_skipped": skipped_internal,
            "raw_candidates": len(raw_candidates),
            "duplicates_removed": duplicates,
            "candidates": len(candidates),
            "search_items_seen": sum(int(item.get("search_items_seen") or 0) for item in route_results),
            "route_scan_summary": scan_route_summary(route_results),
            "online": not bool(args.search_response_json),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
        },
    }
    write_output(args.output, output)
    return 0 if candidates else 1


def extract_smartedu_api_hints(html_text: str, base_url: str) -> list[str]:
    hints: list[str] = []
    patterns = [
        r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+",
        r"['\"]((?:/|//)[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{3,240})['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html_text):
            value = match.group(1) if match.lastindex else match.group(0)
            cleaned = absolute_url(base_url, value)
            if any(term in cleaned.lower() for term in SMARTEDU_API_TERMS):
                hints.append(cleaned)
    return list(dict.fromkeys(hints))[:80]


def extract_script_sources(html_text: str, base_url: str) -> list[str]:
    scripts: list[str] = []
    for match in re.finditer(r"""<script[^>]+src=["']([^"']+)["']""", html_text, re.I):
        scripts.append(absolute_url(base_url, match.group(1)))
    return list(dict.fromkeys(scripts))[:80]


def fetch_script_texts(script_urls: list[str], access_token: str | None, cookie: str | None, extra_headers: dict[str, str], timeout: int, limit: int) -> tuple[str, list[dict[str, str]]]:
    parts: list[str] = []
    failures: list[dict[str, str]] = []
    for url in script_urls[:limit]:
        try:
            parts.append(request_text(url, access_token=access_token, timeout=timeout, cookie=cookie, extra_headers=extra_headers))
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
    return "\n".join(parts), failures


def extract_detail_hints(html_text: str, base_url: str) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    for match in re.finditer(r"(?:contentId|resourceId|resource_id|content_id|courseId)[=:]['\"]?([A-Za-z0-9_-]{6,})", html_text):
        hints.append({"resource_id": match.group(1), "source": "inline-id"})
    for match in re.finditer(r"https?://basic\.smartedu\.cn/([^/]+)/detail\?([^'\"\s<>]+)", html_text):
        query = urllib.parse.parse_qs(match.group(2))
        resource_id = (query.get("contentId") or query.get("id") or [""])[0]
        hints.append(
            {
                "resource_id": resource_id,
                "catalog": match.group(1),
                "source": match.group(0),
            }
        )
    for match in re.finditer(r"['\"]((?:/[^'\"]+)?/detail\?[^'\"]+)['\"]", html_text):
        url = absolute_url(base_url, match.group(1))
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        resource_id = (query.get("contentId") or query.get("id") or [""])[0]
        catalog = (query.get("catalogType") or [""])[0]
        hints.append({"resource_id": resource_id, "catalog": catalog, "source": url})
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in hints:
        key = "|".join([norm(item.get("resource_id")), norm(item.get("catalog")), norm(item.get("source"))])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:80]


def extract_resource_link_hints(html_text: str, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(r"""(?:href|src)=["']([^"']+)["']""", html_text, re.I):
        url = absolute_url(base_url, match.group(1))
        ext = resource_extension(url)
        if ext in RESOURCE_EXTENSIONS:
            links.append({"url": url, "format": ext})
    return list({item["url"]: item for item in links}.values())[:80]


def infer_page_type(html_text: str, url: str, api_hints: list[str], detail_hints: list[dict[str, str]], resource_links: list[dict[str, str]]) -> str:
    lower = f"{html_text[:5000]} {url}".lower()
    if "/detail" in url or detail_hints:
        return "detail_or_detail_capable_page"
    if "librarylist" in lower:
        return "catalog_config_page"
    if api_hints and ("root" in lower or "webpack" in lower or "chunk" in lower):
        return "spa_route_page"
    if resource_links:
        return "static_resource_page"
    if any(term in lower for term in ["search", "resources", "catalog"]):
        return "resource_listing_or_search_page"
    return "unknown"


def run_page_profile(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    page_url = args.url or "https://basic.smartedu.cn/"
    if args.html_file:
        html_text = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
    else:
        html_text = request_text(page_url, access_token=access_token, timeout=args.timeout, cookie=args.cookie, extra_headers=extra_headers)
    script_sources = extract_script_sources(html_text, page_url)
    script_text = ""
    script_failures: list[dict[str, str]] = []
    if args.fetch_scripts:
        script_text, script_failures = fetch_script_texts(script_sources, access_token, args.cookie, extra_headers, args.timeout, args.script_limit)
    combined_text = f"{html_text}\n{script_text}"
    api_hints = extract_smartedu_api_hints(combined_text, page_url)
    detail_hints = extract_detail_hints(combined_text, page_url)
    resource_links = extract_resource_link_hints(combined_text, page_url)
    page_type = infer_page_type(combined_text, page_url, api_hints, detail_hints, resource_links)
    result = {
        "page_profile_schema": "smartedu-page-profile/v1",
        "source_skill": "smartedu-resources",
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "page_url": page_url,
        "page_type": page_type,
        "api_hints": api_hints,
        "detail_hints": detail_hints,
        "resource_link_hints": resource_links,
        "script_sources": script_sources,
        "script_failures": script_failures,
        "recommended_next_actions": [],
        "summary": {
            "api_hints": len(api_hints),
            "detail_hints": len(detail_hints),
            "resource_link_hints": len(resource_links),
            "script_sources": len(script_sources),
            "scripts_fetched": min(len(script_sources), args.script_limit) - len(script_failures) if args.fetch_scripts else 0,
            "script_failures": len(script_failures),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
            "offline_html": bool(args.html_file),
            "fetch_scripts": bool(args.fetch_scripts),
        },
    }
    actions: list[str] = []
    if any("librarylist" in item.lower() for item in api_hints):
        actions.append("route-map")
    if detail_hints:
        actions.append("candidates-from-detail")
    if any("search" in item.lower() or "aggregate" in item.lower() or "combine" in item.lower() for item in api_hints):
        actions.append("search-resources")
    if resource_links:
        actions.append("learning-resource-analyzer")
    result["recommended_next_actions"] = list(dict.fromkeys(actions)) or ["profile_deeper"]
    write_output(args.output, result)
    return 0


def run_site_profile(args: argparse.Namespace) -> int:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    catalogs: list[dict[str, Any]] = []
    catalog_error = ""
    if args.library_list_json:
        data = load_json(args.library_list_json)
        if not isinstance(data, list):
            raise ValueError("library list must be a JSON list")
        catalogs = flatten_catalogs(data)
    elif args.fetch_catalogs:
        try:
            data = request_json(LIBRARY_LIST_URL, access_token=access_token, cookie=args.cookie, extra_headers=extra_headers)
            if isinstance(data, list):
                catalogs = flatten_catalogs(data)
            else:
                catalog_error = "library list response is not a JSON list"
        except Exception as exc:
            catalog_error = str(exc)

    profile = {
        "source_profile_schema": "learning-resource-source-profile/v1",
        "source_skill": "smartedu-resources",
        "source_name": "国家中小学智慧教育平台",
        "site_url": "https://basic.smartedu.cn/",
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "positioning": "站点级学习资源来源；站内各种栏目和资源类型统一由本 skill 转为候选资源。",
        "routing_policy": {
            "as_candidate_source": True,
            "type_binding": False,
            "topic_binding": False,
            "notes": [
                "不要因为用户提到某一种资源类型就固定选择本来源。",
                "当搜索、来源发现或用户明确站点指向 basic.smartedu.cn 时，可把本来源作为候选来源参与排序。",
                "教材是站内资源分支，不是独立外部来源。",
            ],
        },
        "capabilities": [
            {
                "name": "site_profile",
                "command": "site-profile",
                "status": "stable_offline",
                "description": "输出站点能力、资源类型覆盖、授权策略和栏目摘要。",
            },
            {
                "name": "catalog_profile",
                "command": "list-catalogs",
                "status": "stable",
                "description": "读取栏目配置，识别站内栏目、外链栏目和教材内部适配分支。",
            },
            {
                "name": "route_map",
                "command": "route-map",
                "status": "stable_offline",
                "description": "将栏目配置转为栏目路由图，说明页面、搜索 tab、详情模板和内部适配策略。",
            },
            {
                "name": "page_profile",
                "command": "page-profile",
                "status": "stable_offline",
                "description": "从 SmartEdu 页面 HTML/JS 中提取接口、详情 ID、资源链接和下一步动作线索。",
            },
            {
                "name": "catalog_scan",
                "command": "scan-catalog",
                "status": "stable_offline",
                "description": "按单个或少量栏目路由扫描资源候选，可选继续追踪详情。",
            },
            {
                "name": "site_scan",
                "command": "scan-site",
                "status": "stable_offline",
                "description": "按 route-map 批量扫描多个栏目，输出站点级候选索引摘要。",
            },
            {
                "name": "resource_search",
                "command": "search-resources",
                "status": "needs_runtime_auth_or_endpoint_validation",
                "description": "调用或归一化站内搜索结果，输出搜索候选；下载前通常需要继续解析详情。",
            },
            {
                "name": "detail_items",
                "command": "candidates-from-detail",
                "status": "stable",
                "description": "解析详情 JSON 中的 ti_items，将视频、文档、图片、课件等文件项转为候选。",
            },
            {
                "name": "textbook_branch",
                "command": "textbook-candidates",
                "status": "compatibility_adapter",
                "description": "复用早期教材适配能力，对外仍输出 smartedu-resources 候选。",
            },
        ],
        "resource_coverage": {
            "resource_types": DEFAULT_RESOURCE_TYPES,
            "formats": DEFAULT_FORMATS,
            "default_search_tabs": DEFAULT_TAB_CODES,
            "details_expandable": True,
            "direct_download_by_this_skill": False,
        },
        "access_policy": {
            "supports_auth_context": True,
            "auth_inputs": ["SMARTEDU_ACCESS_TOKEN", "SMARTEDU_COOKIE", "SMARTEDU_AUTHORIZATION", "SMARTEDU_HEADERS", "--access-token", "--cookie", "--header"],
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
            "secret_redaction": "输出只记录 auth_context，不写入 token、cookie、authorization 或 header 原文。",
            "login_limited_resources": "可能被标记为 requires_auth，后续交给 downloader 或专门下载团队处理。",
        },
        "catalog_summary": catalog_summary(catalogs) if catalogs else {},
        "catalog_sample": catalogs[: args.catalog_sample] if catalogs else [],
        "warnings": [],
    }
    if catalog_error:
        profile["warnings"].append(f"栏目配置读取失败：{catalog_error}")
    write_output(args.output, profile)
    return 0


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
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
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
    browser_state: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    errors: list[str] = []
    identity = {
        "resource_id": resource_id,
        "catalog": catalog,
        "tab_code": catalog,
        "content_type": "national_lesson" if catalog == "syncClassroom" else "",
        "resource_type": "",
    }
    for attempt in detail_urls_for_identity(identity):
        url = attempt["url"]
        try:
            return request_json(url, access_token=access_token, cookie=cookie, extra_headers=extra_headers)
        except Exception as exc:
            errors.append(str(exc))
            if browser_state:
                detail, status, _content_type, error = browser_request_json_status(url, browser_state, timeout=timeout)
                if detail is not None:
                    return detail
                errors.append(f"browser_state {url}: status={status} error={error}")
    raise RuntimeError("; ".join(errors))


def detail_identity_from_url(url: str) -> dict[str, str]:
    identity = identity_from_detail_page_url(url)
    if identity.get("resource_id"):
        return {
            "resource_id": identity.get("resource_id", ""),
            "catalog": identity.get("catalog") or identity.get("tab_code") or "syncClassroom",
            "sub_catalog": identity.get("sub_catalog", ""),
            "content_type": identity.get("content_type", ""),
        }
    raise ValueError(f"无法从 SmartEdu URL 识别资源 ID: {url}")


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
    detail_contexts: list[dict[str, str]] = []
    url_context = detail_identity_from_url(args.url) if args.url else None
    default_context = {
        "catalog": (url_context or {}).get("catalog") or args.catalog or "syncClassroom",
        "sub_catalog": (url_context or {}).get("sub_catalog") or args.sub_catalog or "",
    }
    if args.detail_json:
        for path in args.detail_json:
            data = load_json(path)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        details.append(item)
                        detail_contexts.append(default_context)
            elif isinstance(data, dict):
                details.append(data)
                detail_contexts.append(default_context)
    elif args.url:
        identity = detail_identity_from_url(args.url)
        details.append(
            fetch_detail(
                identity["resource_id"],
                identity["catalog"],
                access_token,
                cookie=args.cookie,
                extra_headers=extra_headers,
                browser_state=args.browser_state,
                timeout=args.timeout,
            )
        )
        detail_contexts.append({"catalog": identity["catalog"], "sub_catalog": identity.get("sub_catalog", "")})
    elif args.resource_id and args.catalog:
        details.append(
            fetch_detail(
                args.resource_id,
                args.catalog,
                access_token,
                cookie=args.cookie,
                extra_headers=extra_headers,
                browser_state=args.browser_state,
                timeout=args.timeout,
            )
        )
        detail_contexts.append({"catalog": args.catalog, "sub_catalog": args.sub_catalog or ""})
    else:
        print("error: provide --detail-json, --url, or both --catalog and --resource-id", file=sys.stderr)
        return 2

    filters = load_task_filters(args.task_json)
    all_candidates: list[dict[str, Any]] = []
    items_seen = 0
    skipped = 0
    for index, detail in enumerate(details[: args.limit]):
        context = detail_contexts[index] if index < len(detail_contexts) else {"catalog": args.catalog or "syncClassroom", "sub_catalog": args.sub_catalog or ""}
        candidates, seen, failed = candidates_from_detail(detail, context["catalog"], context.get("sub_catalog", ""), filters)
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
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
            "browser_state_context": bool(args.browser_state),
        },
    }
    write_output(args.output, result)
    return 0 if all_candidates else 1


def fetch_search_results(args: argparse.Namespace, filters: dict[str, Any]) -> Any:
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    payload = search_payload(args, filters)
    tag_filters = payload.get("combine_resources", [])
    if args.search_url:
        return request_json(args.search_url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers)
    errors: list[str] = []
    # 第一步：带 combine_resources tag 筛选搜索
    for url in SEARCH_URLS:
        try:
            data = request_json(url, access_token=access_token, payload=payload, cookie=args.cookie, extra_headers=extra_headers)
            items = extract_search_items(data, args.limit)
            if items or not tag_filters:
                return data
            # 带筛选搜到0条目，降级为无筛选宽搜索，后面由本地硬过滤补位
            break
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    # 第二步：去掉 combine_resources 做宽搜索
    payload_no_filter = dict(payload)
    payload_no_filter["combine_resources"] = []
    for url in SEARCH_URLS:
        try:
            return request_json(url, access_token=access_token, payload=payload_no_filter, cookie=args.cookie, extra_headers=extra_headers)
        except Exception as exc:
            errors.append(f"{url}(no-filter): {exc}")
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
    items = filter_search_items_by_tags(items, filters)
    candidates: list[dict[str, Any]] = []
    details_fetched = 0
    detail_failures: list[dict[str, Any]] = []
    detail_items_seen = 0
    detail_items_skipped = 0
    if args.fetch_details:
        for item in items:
            detail, identity, error, probe = detail_for_search_item(item, args, access_token, extra_headers)
            detail_summary = detail_summary_for_probe(probe)
            if detail is None:
                fallback = search_item_to_candidate(item, query, filters)
                fallback.setdefault("raw", {}).setdefault("warnings", []).append(f"详情追踪失败：{error or 'unknown error'}")
                annotate_candidate_detail(fallback, detail_summary)
                candidates.append(fallback)
                detail_failures.append(detail_failure_for_probe(probe, identity))
                continue
            detail_candidates, seen, skipped = candidates_from_detail(detail, identity["catalog"], identity["sub_catalog"], filters)
            details_fetched += 1
            detail_items_seen += seen
            detail_items_skipped += skipped
            if detail_candidates:
                candidates.extend(annotate_candidate_detail(candidate, detail_summary) for candidate in detail_candidates)
            else:
                fallback = search_item_to_candidate(item, query, filters)
                fallback.setdefault("raw", {}).setdefault("warnings", []).append("详情已获取但未解析出文件项")
                candidates.append(annotate_candidate_detail(fallback, detail_summary))
    else:
        candidates = [search_item_to_candidate(item, query, filters) for item in items]
    result = {
        "candidate_schema": "learning-resource-candidate/v1",
        "source_skill": "smartedu-resources",
        "query": query,
        "filters": filters,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "model_context": search_model_context(items, candidates, query, filters),
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
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
            "browser_state_context": bool(args.browser_state),
            "note": "已开启详情追踪时，候选优先使用详情文件项；未开启或详情失败时，搜索候选仅适合展示和继续展开，下载前应解析真实文件项。",
        },
    }
    if detail_failures:
        result["detail_failures"] = detail_failures
    write_output(args.output, result)
    return 0 if candidates else 1


def run_detail_probe(args: argparse.Namespace) -> int:
    filters = load_task_filters(args.task_json)
    extra_headers = parse_extra_headers(args.header)
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    query = args.query or norm(filters.get("query") or filters.get("core_topic") or filters.get("subject"))
    if args.search_response_json:
        data = load_json(args.search_response_json)
        online = False
        endpoint = args.search_response_json
    else:
        data = fetch_search_results(args, filters)
        online = True
        endpoint = args.search_url or SEARCH_URLS[0]
    items = extract_search_items(data, args.limit)
    items = filter_search_items_by_tags(items, filters)
    probes = [probe_detail_for_search_item(item, args, access_token, extra_headers) for item in items]
    matrix = detail_probe_matrix(probes)
    status_counts = count_values([norm(item.get("detail_status")) for item in probes])
    access_policy_counts = count_values([norm(item.get("detail_access_policy")) for item in probes])
    result = {
        "detail_probe_schema": "smartedu-detail-probe/v1",
        "source_skill": "smartedu-resources",
        "query": query,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "online_search": online,
        "search_endpoint": endpoint,
        "probes": probes,
        "detail_matrix": matrix,
        "summary": {
            "search_items_seen": len(items),
            "probes": len(probes),
            "matrix_rows": len(matrix),
            "status_counts": status_counts,
            "access_policy_counts": access_policy_counts,
            "details_accessible": sum(status_counts.get(key, 0) for key in ["ok_with_file_items", "ok_no_file_items"]),
            "requires_auth": status_counts.get("requires_auth", 0),
            "file_items": sum(int(item.get("file_item_count") or 0) for item in probes),
            "parsed_candidates": sum(int(item.get("parsed_candidate_count") or 0) for item in probes),
            "auth_context": has_runtime_auth_context(access_token, args.cookie, extra_headers, args),
            "browser_state_context": bool(args.browser_state),
        },
    }
    write_output(args.output, result)
    return 0 if probes else 1


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

    profile = sub.add_parser("site-profile", help="输出 SmartEdu 站点能力画像")
    profile.add_argument("--library-list-json", help="本地 librarylist JSON；提供后会附带栏目摘要")
    profile.add_argument("--fetch-catalogs", action="store_true", help="联网读取官方栏目配置并附带栏目摘要")
    profile.add_argument("--catalog-sample", type=int, default=8, help="最多输出多少条栏目样例")
    profile.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    profile.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    profile.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    profile.add_argument("-o", "--output", help="写入 JSON 文件")
    profile.set_defaults(func=run_site_profile)

    catalogs = sub.add_parser("list-catalogs", help="输出 SmartEdu 栏目画像")
    catalogs.add_argument("--library-list-json", help="本地 librarylist JSON；省略时抓取官方公开配置")
    catalogs.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    catalogs.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    catalogs.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    catalogs.add_argument("-o", "--output", help="写入 JSON 文件")
    catalogs.set_defaults(func=run_list_catalogs)

    route_map = sub.add_parser("route-map", help="输出 SmartEdu 栏目路由图")
    route_map.add_argument("--library-list-json", help="本地 librarylist JSON；省略时抓取官方公开配置")
    route_map.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    route_map.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    route_map.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    route_map.add_argument("-o", "--output", help="写入 JSON 文件")
    route_map.set_defaults(func=run_route_map)

    site_index = sub.add_parser("site-index", help="输出 SmartEdu 全站 route 覆盖和可选扫描候选索引")
    site_index.add_argument("--route-map-json", help="route-map 输出 JSON；省略时通过 librarylist 构建")
    site_index.add_argument("--library-list-json", help="本地 librarylist JSON；未提供 route-map 时使用")
    site_index.add_argument("--site-scan-json", help="可选 scan-site 输出 JSON；提供后把候选、失败和扫描摘要并入索引")
    site_index.add_argument("--route-id", help="只索引指定 route_id")
    site_index.add_argument("--catalog", help="只索引指定 catalog")
    site_index.add_argument("--sub-catalog", help="只索引指定 sub_catalog")
    site_index.add_argument("--type", help="只索引指定栏目 type")
    site_index.add_argument("--title", help="只索引标题包含该文本的栏目")
    site_index.add_argument("--route-limit", type=int, default=0, help="最多索引多少条栏目路由；0 表示全部")
    site_index.add_argument("--all-routes", action="store_true", help="索引全部匹配 route，等同于 --route-limit 0")
    site_index.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    site_index.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    site_index.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    site_index.add_argument("-o", "--output", help="写入 JSON 文件")
    site_index.set_defaults(func=run_site_index)

    page_profile = sub.add_parser("page-profile", help="分析 SmartEdu 页面 HTML/JS 结构线索")
    page_profile.add_argument("--url", help="页面 URL，默认 https://basic.smartedu.cn/")
    page_profile.add_argument("--html-file", help="本地 HTML 文件；用于离线分析或测试")
    page_profile.add_argument("--fetch-scripts", action="store_true", help="抓取页面引用的 JS 文件并一起分析接口线索")
    page_profile.add_argument("--script-limit", type=int, default=8, help="最多抓取多少个 JS 文件")
    page_profile.add_argument("--timeout", type=int, default=20, help="联网读取页面时的超时秒数")
    page_profile.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    page_profile.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    page_profile.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    page_profile.add_argument("-o", "--output", help="写入 JSON 文件")
    page_profile.set_defaults(func=run_page_profile)

    scan = sub.add_parser("scan-catalog", help="按栏目路由扫描 SmartEdu 资源候选")
    scan.add_argument("--route-map-json", help="route-map 输出 JSON；省略时通过 librarylist 构建")
    scan.add_argument("--library-list-json", help="本地 librarylist JSON；未提供 route-map 时使用")
    scan.add_argument("--route-id", help="只扫描指定 route_id")
    scan.add_argument("--catalog", help="只扫描指定 catalog")
    scan.add_argument("--sub-catalog", help="只扫描指定 sub_catalog")
    scan.add_argument("--type", help="只扫描指定栏目 type")
    scan.add_argument("--title", help="只扫描标题包含该文本的栏目")
    scan.add_argument("--route-limit", type=int, default=5, help="最多扫描多少条栏目路由")
    scan.add_argument("--all-routes", action="store_true", help="扫描全部匹配 route，等同于 --route-limit 0")
    scan.add_argument("--query", help="扫描关键词；省略时使用栏目标题")
    scan.add_argument("--search-response-json", help="本地 SmartEdu 搜索响应 JSON；用于离线扫描测试")
    scan.add_argument("--search-url", help="自定义 SmartEdu 搜索接口 URL")
    scan.add_argument("--fetch-details", action="store_true", help="对扫描候选继续追踪详情 JSON 并解析 ti_items")
    scan.add_argument("--detail-dir", help="本地详情 JSON 目录；支持 {id}.json、{catalog}-{id}.json、{catalog}/{id}.json")
    scan.add_argument("--offline-details-only", action="store_true", help="只使用 --detail-dir，不联网抓取缺失详情")
    scan.add_argument("--browser-state", help="可选 Playwright storage state；公开详情失败时用浏览器会话补请求")
    scan.add_argument("--timeout", type=int, default=20, help="详情请求超时秒数")
    scan.add_argument("--identity", default="家长", help="SmartEdu identity，默认 家长")
    scan.add_argument("--identity-code", default="GUARDIAN", help="SmartEdu identity_code，默认 GUARDIAN")
    scan.add_argument("--search-type", default="resource", help="resource_search_type，默认 resource")
    scan.add_argument("--origin", default="basic", help="SmartEdu origin，默认 basic")
    scan.add_argument("--order-field", default="_score", help="排序字段")
    scan.add_argument("--order-direction", default="desc", help="排序方向")
    scan.add_argument("--offset", type=int, default=0, help="分页 offset")
    scan.add_argument("--limit", type=int, default=12, help="每条 route 最多输出候选数量")
    scan.add_argument("--cross-tenant", action="store_true", help="允许跨租户搜索")
    scan.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    scan.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    scan.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    scan.add_argument("-o", "--output", help="写入 JSON 文件")
    scan.set_defaults(func=run_scan_catalog)

    site_scan = sub.add_parser("scan-site", help="按 route-map 批量扫描 SmartEdu 多栏目候选")
    site_scan.add_argument("--route-map-json", help="route-map 输出 JSON；省略时通过 librarylist 构建")
    site_scan.add_argument("--library-list-json", help="本地 librarylist JSON；未提供 route-map 时使用")
    site_scan.add_argument("--route-id", help="只扫描指定 route_id")
    site_scan.add_argument("--catalog", help="只扫描指定 catalog")
    site_scan.add_argument("--sub-catalog", help="只扫描指定 sub_catalog")
    site_scan.add_argument("--type", help="只扫描指定栏目 type")
    site_scan.add_argument("--title", help="只扫描标题包含该文本的栏目")
    site_scan.add_argument("--route-limit", type=int, default=10, help="最多扫描多少条栏目路由")
    site_scan.add_argument("--all-routes", action="store_true", help="扫描全部匹配 route，等同于 --route-limit 0")
    site_scan.add_argument("--query", help="扫描关键词；省略时使用栏目标题")
    site_scan.add_argument("--search-response-json", help="本地 SmartEdu 搜索响应 JSON；用于离线扫描测试")
    site_scan.add_argument("--search-url", help="自定义 SmartEdu 搜索接口 URL")
    site_scan.add_argument("--fetch-details", action="store_true", help="对扫描候选继续追踪详情 JSON 并解析 ti_items")
    site_scan.add_argument("--detail-dir", help="本地详情 JSON 目录；支持 {id}.json、{catalog}-{id}.json、{catalog}/{id}.json")
    site_scan.add_argument("--offline-details-only", action="store_true", help="只使用 --detail-dir，不联网抓取缺失详情")
    site_scan.add_argument("--browser-state", help="可选 Playwright storage state；公开详情失败时用浏览器会话补请求")
    site_scan.add_argument("--timeout", type=int, default=20, help="详情请求超时秒数")
    site_scan.add_argument("--continue-on-error", action="store_true", help="某条 route 扫描失败时继续扫描后续 route")
    site_scan.add_argument("--identity", default="家长", help="SmartEdu identity，默认 家长")
    site_scan.add_argument("--identity-code", default="GUARDIAN", help="SmartEdu identity_code，默认 GUARDIAN")
    site_scan.add_argument("--search-type", default="resource", help="resource_search_type，默认 resource")
    site_scan.add_argument("--origin", default="basic", help="SmartEdu origin，默认 basic")
    site_scan.add_argument("--order-field", default="_score", help="排序字段")
    site_scan.add_argument("--order-direction", default="desc", help="排序方向")
    site_scan.add_argument("--offset", type=int, default=0, help="分页 offset")
    site_scan.add_argument("--limit", type=int, default=12, help="每条 route 最多输出候选数量")
    site_scan.add_argument("--cross-tenant", action="store_true", help="允许跨租户搜索")
    site_scan.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    site_scan.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    site_scan.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    site_scan.add_argument("-o", "--output", help="写入 JSON 文件")
    site_scan.set_defaults(func=run_scan_site)

    detail = sub.add_parser("candidates-from-detail", help="从 SmartEdu 详情 JSON 输出标准候选")
    detail.add_argument("--detail-json", action="append", help="本地 SmartEdu detail JSON，可重复")
    detail.add_argument("--url", help="SmartEdu 详情页 URL，例如 syncClassroom/classActivity、qualityCourse、tchMaterial")
    detail.add_argument("--catalog", help="栏目，例如 qualityCourse、syncClassroom、family")
    detail.add_argument("--sub-catalog", help="子栏目，例如 course、prepare_lesson")
    detail.add_argument("--resource-id", help="资源 ID；与 --catalog 一起尝试抓取详情")
    detail.add_argument("--task-json", help="可选任务 JSON，用于传递 filters")
    detail.add_argument("--query", help="原始查询")
    detail.add_argument("--limit", type=int, default=50, help="最多处理详情数量")
    detail.add_argument("--browser-state", help="可选 Playwright storage state；公开详情失败时用浏览器会话补请求")
    detail.add_argument("--timeout", type=int, default=20, help="详情请求超时秒数")
    detail.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    detail.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    detail.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    detail.add_argument("-o", "--output", help="写入 JSON 文件")
    detail.set_defaults(func=run_candidates_from_detail)

    detail_probe = sub.add_parser("detail-probe", help="低频探测 SmartEdu 搜索候选能否展开详情 JSON")
    detail_probe.add_argument("--query", help="搜索关键词；省略时从 --task-json 的 filters 中推断")
    detail_probe.add_argument("--task-json", help="可选任务 JSON，用于传递 filters")
    detail_probe.add_argument("--tab-code", action="append", help="SmartEdu tab_code，可重复或逗号分隔")
    detail_probe.add_argument("--search-response-json", help="本地 SmartEdu 搜索响应 JSON；用于离线 probe")
    detail_probe.add_argument("--search-url", help="自定义 SmartEdu 搜索接口 URL")
    detail_probe.add_argument("--detail-dir", help="本地详情 JSON 目录；支持 {id}.json、{catalog}-{id}.json、{catalog}/{id}.json")
    detail_probe.add_argument("--offline-details-only", action="store_true", help="只使用 --detail-dir，不联网抓取缺失详情")
    detail_probe.add_argument("--identity", default="家长", help="SmartEdu identity，默认 家长")
    detail_probe.add_argument("--identity-code", default="GUARDIAN", help="SmartEdu identity_code，默认 GUARDIAN")
    detail_probe.add_argument("--search-type", default="resource", help="resource_search_type，默认 resource")
    detail_probe.add_argument("--origin", default="basic", help="SmartEdu origin，默认 basic")
    detail_probe.add_argument("--order-field", default="_score", help="排序字段")
    detail_probe.add_argument("--order-direction", default="desc", help="排序方向")
    detail_probe.add_argument("--offset", type=int, default=0, help="分页 offset")
    detail_probe.add_argument("--limit", type=int, default=12, help="最多探测多少个搜索候选")
    detail_probe.add_argument("--cross-tenant", action="store_true", help="允许跨租户搜索")
    detail_probe.add_argument("--timeout", type=int, default=20, help="详情请求超时秒数")
    detail_probe.add_argument("--browser-state", help="可选 Playwright storage state；公开详情失败时用浏览器会话补请求")
    detail_probe.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    detail_probe.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    detail_probe.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    detail_probe.add_argument("-o", "--output", help="写入 JSON 文件")
    detail_probe.set_defaults(func=run_detail_probe)

    search = sub.add_parser("search-resources", help="搜索 SmartEdu 资源并输出标准候选")
    search.add_argument("--query", help="搜索关键词；省略时从 --task-json 的 filters 中推断")
    search.add_argument("--task-json", help="可选任务 JSON，用于传递 filters")
    search.add_argument("--tab-code", action="append", help="SmartEdu tab_code，可重复或逗号分隔")
    search.add_argument("--search-response-json", help="本地 SmartEdu 搜索响应 JSON；用于离线归一化测试")
    search.add_argument("--search-url", help="自定义 SmartEdu 搜索接口 URL")
    search.add_argument("--fetch-details", action="store_true", help="对搜索候选继续追踪详情 JSON 并解析 ti_items")
    search.add_argument("--detail-dir", help="本地详情 JSON 目录；支持 {id}.json、{catalog}-{id}.json、{catalog}/{id}.json")
    search.add_argument("--offline-details-only", action="store_true", help="只使用 --detail-dir，不联网抓取缺失详情")
    search.add_argument("--browser-state", help="可选 Playwright storage state；公开详情失败时用浏览器会话补请求")
    search.add_argument("--timeout", type=int, default=20, help="详情请求超时秒数")
    search.add_argument("--identity", default="家长", help="SmartEdu identity，默认 家长")
    search.add_argument("--identity-code", default="GUARDIAN", help="SmartEdu identity_code，默认 GUARDIAN")
    search.add_argument("--search-type", default="resource", help="resource_search_type，默认 resource")
    search.add_argument("--origin", default="basic", help="SmartEdu origin，默认 basic")
    search.add_argument("--order-field", default="_score", help="排序字段")
    search.add_argument("--order-direction", default="desc", help="排序方向")
    search.add_argument("--offset", type=int, default=0, help="分页 offset")
    search.add_argument("--limit", type=int, default=12, help="最多输出候选数量")
    search.add_argument("--cross-tenant", action="store_true", default=True, help="允许跨租户搜索；默认开启以匹配 SmartEdu 前端请求")
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
