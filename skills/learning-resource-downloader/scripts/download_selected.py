#!/usr/bin/env python3
"""Download selected learning resource options into a work cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SAFE_EXTENSIONS = {
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
    "gif",
    "webp",
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "avi",
    "zip",
    "html",
    "m3u8",
}


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_name(value: Any, fallback: str = "resource", limit: int = 90) -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text or fallback)[:limit]


def parse_selection(value: str, options: list[dict[str, Any]]) -> list[str]:
    if value.lower() == "all":
        return [str(option.get("option_id")) for option in options]
    parts = re.split(r"[,，\s]+", value.strip())
    return [part.upper() for part in parts if part]


def option_map(options: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(option.get("option_id")).upper(): option for option in options if option.get("option_id")}


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


def build_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"User-Agent": "learning-resource-agent/0.1"}
    authorization = os.environ.get("SMARTEDU_AUTHORIZATION")
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    cookie = args.cookie or os.environ.get("SMARTEDU_COOKIE")
    if authorization:
        headers["Authorization"] = authorization
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        headers["accessToken"] = access_token
    if cookie:
        headers["Cookie"] = cookie
    headers.update(parse_extra_headers(args.header))
    return headers


def has_auth_context(args: argparse.Namespace) -> bool:
    return bool(
        args.access_token
        or args.cookie
        or args.header
        or os.environ.get("SMARTEDU_ACCESS_TOKEN")
        or os.environ.get("SMARTEDU_COOKIE")
        or os.environ.get("SMARTEDU_AUTHORIZATION")
        or os.environ.get("SMARTEDU_HEADERS")
    )


def extension_for(option: dict[str, Any], url: str, content_type: str | None = None) -> str:
    fmt = str(option.get("format") or "").lower().lstrip(".")
    if fmt in SAFE_EXTENSIONS:
        return "html" if fmt == "html" else fmt
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    if suffix in SAFE_EXTENSIONS:
        return suffix
    guessed = mimetypes.guess_extension(content_type or "") if content_type else None
    if guessed:
        guessed = guessed.lstrip(".")
        if guessed in SAFE_EXTENSIONS:
            return guessed
    return "html"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_urls(option: dict[str, Any]) -> list[str]:
    candidate = option.get("candidate") or {}
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    urls: list[str] = []
    for url in [option.get("source_url"), candidate.get("source_url"), *(raw.get("url_candidates") or [])]:
        if isinstance(url, str) and url and url not in urls:
            urls.append(url)
    return urls


def should_skip(option: dict[str, Any], allow_auth: bool, auth_context: bool) -> str | None:
    candidate = option.get("candidate") or {}
    requires_auth = bool(option.get("requires_auth") or candidate.get("requires_auth"))
    if requires_auth and not allow_auth:
        return "需要登录或授权访问"
    if requires_auth and not auth_context:
        return "需要授权上下文"
    raw = candidate.get("raw") or {}
    warnings = " ".join(str(item) for item in raw.get("warnings") or [])
    if any(term in warnings for term in ["下载器", "破解", "成人"]):
        return "候选存在风险提示"
    return None


def request_headers(headers: dict[str, str], extra: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(headers)
    merged.update(extra or {})
    return merged


def probe_url(url: str, timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        return {"url": str(url), "ok": False, "error": "只支持 http/https 探测"}
    for method, extra in [("HEAD", {}), ("GET", {"Range": "bytes=0-0"})]:
        try:
            request = urllib.request.Request(str(url), method=method, headers=request_headers(headers, extra))
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return {
                    "url": str(url),
                    "ok": 200 <= response.status < 400,
                    "status": response.status,
                    "method": method,
                    "content_type": response.headers.get("Content-Type"),
                    "content_length": int(response.headers.get("Content-Length") or 0) or None,
                }
        except Exception as exc:
            last_error = str(exc)
    return {"url": str(url), "ok": False, "error": last_error}


def probe_option(option: dict[str, Any], timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    candidate = option.get("candidate") or {}
    urls = candidate_urls(option)
    if not urls:
        raise ValueError("缺少 source_url")
    results = [probe_url(url, timeout, headers) for url in urls]
    accessible = next((item for item in results if item.get("ok")), None)
    return {
        "option_id": option.get("option_id"),
        "title": option.get("title"),
        "source_url": accessible.get("url") if accessible else None,
        "format": option.get("format") or candidate.get("format"),
        "resource_type": option.get("resource_type") or candidate.get("resource_type"),
        "accessible": bool(accessible),
        "url_results": results,
        "candidate": candidate,
    }


def download_url(url: str, dest: Path, timeout: int, max_bytes: int, headers: dict[str, str]) -> tuple[int, str | None]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type")
        total = 0
        with dest.open("wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"文件超过大小限制 {max_bytes} bytes")
                fh.write(chunk)
    return total, content_type


def download_option(option: dict[str, Any], downloads_dir: Path, timeout: int, max_bytes: int, headers: dict[str, str]) -> dict[str, Any]:
    candidate = option.get("candidate") or {}
    urls = candidate_urls(option)
    if not urls:
        raise ValueError("缺少 source_url")

    downloads_dir.mkdir(parents=True, exist_ok=True)
    title = safe_name(option.get("title") or candidate.get("title") or option.get("option_id"))
    resource_id = safe_name(option.get("resource_id") or candidate.get("resource_id") or option.get("option_id"), limit=24)
    errors: list[str] = []
    chosen_url = ""
    dest: Path | None = None
    size = 0
    content_type = None
    final_ext = ""
    for url in urls:
        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme not in {"http", "https"}:
            errors.append(f"{url}: 只支持 http/https 下载")
            continue
        ext = extension_for(option, str(url))
        attempt_dest = downloads_dir / f"{title}_{resource_id}.{ext}"
        try:
            size, content_type = download_url(str(url), attempt_dest, timeout, max_bytes, headers)
            final_ext = extension_for(option, str(url), content_type)
            if final_ext != ext:
                final_dest = attempt_dest.with_suffix(f".{final_ext}")
                attempt_dest.rename(final_dest)
                attempt_dest = final_dest
            chosen_url = str(url)
            dest = attempt_dest
            break
        except Exception as exc:
            if attempt_dest.exists():
                attempt_dest.unlink()
            errors.append(f"{url}: {exc}")
    if dest is None:
        raise ValueError("; ".join(errors))
    return {
        "option_id": option.get("option_id"),
        "title": option.get("title"),
        "source_url": chosen_url,
        "local_file": str(dest),
        "format": final_ext,
        "resource_type": option.get("resource_type"),
        "size": size,
        "sha256": sha256_file(dest),
        "content_type": content_type,
        "candidate": candidate,
    }


def run(args: argparse.Namespace) -> int:
    data = load_json(args.input)
    options = data.get("options") or []
    if not isinstance(options, list):
        print("error: options must be a list", file=sys.stderr)
        return 2

    selected_ids = parse_selection(args.select, options)
    options_by_id = option_map(options)
    work_dir = Path(args.work_dir)
    downloads_dir = work_dir / "downloads"
    auth_context = has_auth_context(args)
    headers = build_headers(args)

    downloaded: list[dict[str, Any]] = []
    probed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for selected_id in selected_ids:
        option = options_by_id.get(selected_id)
        if not option:
            failures.append({"option_id": selected_id, "title": None, "source_url": None, "error": "选择编号不存在", "candidate": {}})
            continue

        skip_reason = should_skip(option, args.allow_auth, auth_context)
        if skip_reason:
            skipped.append(
                {
                    "option_id": option.get("option_id"),
                    "title": option.get("title"),
                    "reason": skip_reason,
                    "candidate": option.get("candidate") or {},
                }
            )
            continue

        try:
            if args.probe_only:
                probed.append(probe_option(option, args.timeout, headers))
            else:
                downloaded.append(download_option(option, downloads_dir, args.timeout, args.max_bytes, headers))
        except Exception as exc:
            failures.append(
                {
                    "option_id": option.get("option_id"),
                    "title": option.get("title"),
                    "source_url": option.get("source_url"),
                    "error": str(exc),
                    "candidate": option.get("candidate") or {},
                }
            )

    accessible_probes = [item for item in probed if item.get("accessible")]
    if (downloaded or accessible_probes) and not skipped and not failures and len(accessible_probes) == len(probed):
        status = "completed"
    elif downloaded or accessible_probes:
        status = "partial"
    else:
        status = "failed"

    result = {
        "download_schema": "learning-resource-download/v1",
        "status": status,
        "requested": selected_ids,
        "downloaded_files": downloaded,
        "probed": probed,
        "skipped": skipped,
        "failures": failures,
        "work_dir": str(work_dir),
        "auth_context": auth_context,
        "probe_only": bool(args.probe_only),
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if downloaded or accessible_probes else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Download selected learning resources into work cache")
    parser.add_argument("input", help="Selection JSON file, or '-' for stdin")
    parser.add_argument("--select", required=True, help="Option ids, e.g. A,B or all")
    parser.add_argument("--work-dir", default=".learning-resource-work", help="Work cache directory")
    parser.add_argument("-o", "--output", help="Write download JSON to this file")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    parser.add_argument("--max-bytes", type=int, default=200 * 1024 * 1024, help="Maximum file size")
    parser.add_argument("--allow-auth", action="store_true", help="允许使用授权上下文下载 requires_auth 候选")
    parser.add_argument("--probe-only", action="store_true", help="只探测候选 URL 可访问性，不保存文件")
    parser.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    parser.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    parser.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
