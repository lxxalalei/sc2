#!/usr/bin/env python3
"""Download selected learning resource options into a work cache."""

from __future__ import annotations

import argparse
import hashlib
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


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


SAFE_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "txt",
    "json",
    "srt",
    "superboard",
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
    "ts",
}

OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


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
    mapped: dict[str, dict[str, Any]] = {}
    for index, option in enumerate(options):
        option_value = option.get("option_id")
        if not option_value:
            continue
        key = str(option_value).upper()
        mapped[key] = option
        if str(option_value).isdigit() and index < len(OPTION_LETTERS):
            mapped.setdefault(OPTION_LETTERS[index], option)
    return mapped


def option_id(index: int) -> str:
    return str(index + 1)


def user_facing_url(candidate: dict[str, Any]) -> str:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    detail_page = raw.get("detail_page")
    if isinstance(detail_page, str) and detail_page.startswith(("http://", "https://")):
        return detail_page
    return str(candidate.get("source_url") or "")


def candidate_to_option(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "option_id": option_id(index),
        "title": candidate.get("title") or f"资源 {index + 1}",
        "source_name": candidate.get("source_name") or candidate.get("provider") or "",
        "source_url": user_facing_url(candidate),
        "download_url": candidate.get("source_url"),
        "resource_id": candidate.get("resource_id"),
        "resource_type": candidate.get("resource_type"),
        "format": candidate.get("format"),
        "downloadable": bool(candidate.get("downloadable")),
        "requires_auth": bool(candidate.get("requires_auth")),
        "official": bool(candidate.get("official")),
        "candidate": candidate,
    }


def input_options(data: dict[str, Any]) -> list[dict[str, Any]]:
    options = data.get("options")
    if isinstance(options, list):
        return options
    candidates = data.get("candidates")
    if isinstance(candidates, list):
        return [candidate_to_option(candidate, index) for index, candidate in enumerate(candidates) if isinstance(candidate, dict)]
    return []


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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://basic.smartedu.cn",
        "Referer": "https://basic.smartedu.cn/",
    }
    authorization = os.environ.get("SMARTEDU_AUTHORIZATION")
    access_token = args.access_token or os.environ.get("SMARTEDU_ACCESS_TOKEN")
    cookie = args.cookie or os.environ.get("SMARTEDU_COOKIE")
    if access_token and "SMARTEDU_ACCESS_TOKEN" not in os.environ:
        os.environ["SMARTEDU_ACCESS_TOKEN"] = access_token
    if authorization:
        headers["Authorization"] = authorization
    if cookie:
        headers["Cookie"] = cookie
    headers.update(parse_extra_headers(args.header))
    return headers


def has_auth_context(args: argparse.Namespace) -> bool:
    return bool(
        args.access_token
        or args.cookie
        or args.header
        or args.browser_state
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


def content_kind(content_type: str | None) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    if value in {"application/pdf", "application/x-pdf"}:
        return "pdf"
    if value.startswith("image/"):
        return "image"
    if value.startswith("video/") or value in {"application/vnd.apple.mpegurl", "application/x-mpegurl"}:
        return "video"
    if value in {"text/html", "application/xhtml+xml"}:
        return "html"
    if value in {"application/json", "text/json"}:
        return "json"
    if value.startswith("text/"):
        return "text"
    return ""


def sniff_file_kind(path: Path) -> str:
    try:
        head = path.read_bytes()[:512]
    except OSError:
        return ""
    stripped = head.lstrip().lower()
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"GIF8") or head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "image"
    if stripped.startswith((b"<!doctype html", b"<html", b"<script", b"<head")):
        return "html"
    if stripped.startswith((b"{", b"[")):
        return "json"
    return ""


def expected_kind(option: dict[str, Any], ext: str) -> str:
    resource_type = str(option.get("resource_type") or (option.get("candidate") or {}).get("resource_type") or "")
    if ext == "pdf":
        return "pdf"
    if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "image"
    if ext in {"mp4", "mov", "avi", "m3u8", "ts"}:
        return "video"
    if ext == "json":
        return "json"
    if ext in {"txt", "srt", "html"}:
        return "text" if ext != "html" else "html"
    if resource_type == "文档":
        return "pdf" if ext == "pdf" else ""
    if resource_type == "图片":
        return "image"
    if resource_type == "视频":
        return "video"
    return ""


def validate_downloaded_file(path: Path, option: dict[str, Any], expected_ext: str, content_type: str | None) -> None:
    expected = expected_kind(option, expected_ext)
    header_kind = content_kind(content_type)
    file_kind = sniff_file_kind(path)
    if expected and header_kind == "html" and expected != "html":
        raise ValueError(f"响应是 HTML 页面，不是预期的 {expected_ext} 文件")
    if expected == "pdf" and file_kind != "pdf":
        raise ValueError("响应内容不是 PDF 文件")
    if expected == "image" and file_kind and file_kind != "image":
        raise ValueError("响应内容不是图片文件")


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
    for url in [candidate.get("source_url"), *(raw.get("url_candidates") or []), option.get("download_url"), option.get("source_url")]:
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


def smartedu_access_token() -> str:
    return os.environ.get("SMARTEDU_ACCESS_TOKEN") or ""


def should_append_access_token(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(
        marker in host
        for marker in [
            "ykt.cbern.com.cn",
            "ykt.eduyun.cn",
            "smartedu.cn",
        ]
    )


def append_access_token(url: str) -> str:
    token = smartedu_access_token()
    if not token or not should_append_access_token(url):
        return url
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if any(key == "accessToken" for key, _value in query):
        return url
    query.append(("accessToken", token))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def request_url(url: str) -> str:
    return append_access_token(url)


def probe_url(url: str, timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        return {"url": str(url), "ok": False, "error": "只支持 http/https 探测"}
    for method, extra in [("HEAD", {}), ("GET", {"Range": "bytes=0-0"})]:
        try:
            request = urllib.request.Request(request_url(str(url)), method=method, headers=request_headers(headers, extra))
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


def browser_probe_url(url: str, timeout: int, browser_state: str) -> dict[str, Any]:
    state_file = Path(browser_state)
    if not state_file.exists():
        return {"url": str(url), "ok": False, "source": "browser_state", "error": f"missing browser state: {state_file}"}
    script = Path(__file__).resolve().parents[2] / "smartedu-resources" / "scripts" / "smartedu_browser_session.py"
    command = [
        sys.executable,
        str(script),
        "request",
        "--state-json",
        str(state_file),
        "--url",
        str(url),
        "--header",
        "Range: bytes=0-0",
        "--timeout",
        str(timeout),
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    output = completed.stdout.strip()
    if not output:
        return {"url": str(url), "ok": False, "source": "browser_state", "error": completed.stderr.strip() or f"browser request failed: exit {completed.returncode}"}
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return {"url": str(url), "ok": False, "source": "browser_state", "error": f"browser request output decode failed: {exc}"}
    response = data.get("response") if isinstance(data, dict) else {}
    if not isinstance(response, dict):
        return {"url": str(url), "ok": False, "source": "browser_state", "error": "browser request response missing"}
    return {
        "url": str(url),
        "ok": bool(response.get("ok")),
        "source": "browser_state",
        "status": response.get("status"),
        "method": "GET",
        "content_type": response.get("content_type"),
        "content_length": int((response.get("headers") or {}).get("content-length") or 0) or None,
        "error": response.get("error") or "",
    }


def probe_option(option: dict[str, Any], timeout: int, headers: dict[str, str], browser_state: str | None = None) -> dict[str, Any]:
    candidate = option.get("candidate") or {}
    urls = candidate_urls(option)
    if not urls:
        raise ValueError("缺少 source_url")
    results: list[dict[str, Any]] = []
    for url in urls:
        result = probe_url(url, timeout, headers)
        results.append(result)
        if result.get("ok"):
            continue
        if browser_state:
            results.append(browser_probe_url(url, timeout, browser_state))
    accessible = next((item for item in results if item.get("ok")), None)
    return {
        "option_id": option.get("option_id"),
        "title": option.get("title"),
        "source_url": accessible.get("url") if accessible else None,
        "format": option.get("format") or candidate.get("format"),
        "resource_type": option.get("resource_type") or candidate.get("resource_type"),
        "accessible": bool(accessible),
        "browser_state_context": bool(browser_state),
        "url_results": results,
        "candidate": candidate,
    }


def download_url(url: str, dest: Path, timeout: int, max_bytes: int, headers: dict[str, str]) -> tuple[int, str | None]:
    request = urllib.request.Request(request_url(url), headers=headers)
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


def read_url_bytes(url: str, timeout: int, headers: dict[str, str]) -> tuple[bytes, str | None]:
    request = urllib.request.Request(request_url(url), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type")


def m3u8_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def choose_media_playlist_url(playlist_url: str, text: str) -> str:
    if not text.lstrip().startswith("#EXTM3U"):
        raise ValueError("响应不是 m3u8 播放列表")
    lines = m3u8_lines(text)
    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            for candidate in lines[index + 1 :]:
                if not candidate.startswith("#"):
                    return urllib.parse.urljoin(playlist_url, candidate)
    return playlist_url


def parse_m3u8_attributes(value: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    current = ""
    in_quote = False
    parts: list[str] = []
    for char in value:
        if char == '"':
            in_quote = not in_quote
        if char == "," and not in_quote:
            parts.append(current)
            current = ""
        else:
            current += char
    if current:
        parts.append(current)
    for part in parts:
        if "=" not in part:
            continue
        key, attr_value = part.split("=", 1)
        attrs[key.strip().upper()] = attr_value.strip().strip('"')
    return attrs


def media_key(playlist_url: str, lines: list[str]) -> dict[str, str] | None:
    key_line = next((line for line in lines if line.startswith("#EXT-X-KEY:")), None)
    if not key_line:
        return None
    attrs = parse_m3u8_attributes(key_line.split(":", 1)[1])
    method = attrs.get("METHOD", "").upper()
    if method == "NONE":
        return None
    if method != "AES-128":
        raise ValueError(f"暂不支持加密 m3u8 方法: {method or 'unknown'}")
    uri = attrs.get("URI")
    if not uri:
        raise ValueError("加密 m3u8 缺少 key URI")
    iv = attrs.get("IV") or "0x00000000000000000000000000000000"
    return {"method": method, "uri": urllib.parse.urljoin(playlist_url, uri), "iv": iv.removeprefix("0x").removeprefix("0X")}


def media_segment_urls(playlist_url: str, text: str) -> tuple[list[str], dict[str, str] | None]:
    if not text.lstrip().startswith("#EXTM3U"):
        raise ValueError("响应不是 m3u8 播放列表")
    lines = m3u8_lines(text)
    key = media_key(playlist_url, lines)
    segments = [urllib.parse.urljoin(playlist_url, line) for line in lines if not line.startswith("#")]
    if not segments:
        raise ValueError("m3u8 中未找到媒体分片")
    return segments, key


def decrypt_aes128_segment(segment: bytes, key: bytes, iv_hex: str) -> bytes:
    if len(key) != 16:
        raise ValueError(f"AES-128 key 长度异常: {len(key)} bytes")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", iv_hex or ""):
        raise ValueError("AES-128 IV 格式异常")
    completed = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv_hex],
        input=segment,
        capture_output=True,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"AES-128 分片解密失败: {error or completed.returncode}")
    return completed.stdout


def decrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    completed = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-ecb", "-K", key.hex()],
        input=data,
        capture_output=True,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"AES-ECB key 解密失败: {error or completed.returncode}")
    return completed.stdout


def fetch_json(url: str, timeout: int, headers: dict[str, str]) -> dict[str, Any]:
    data, _content_type = read_url_bytes(url, timeout, headers)
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("响应 JSON 不是对象")
    return parsed


def fetch_hls_decryption_key(key_info: dict[str, str], timeout: int, headers: dict[str, str]) -> bytes:
    key_url = key_info["uri"]
    key_id = key_url.rstrip("/").rsplit("/", 1)[-1]
    nonce_payload = fetch_json(f"{key_url}/signs", timeout, headers)
    nonce = str(nonce_payload.get("nonce") or "")
    if not nonce:
        raise ValueError("视频 key signs 响应缺少 nonce")
    sign = hashlib.md5((nonce + key_id).encode("utf-8")).hexdigest()[:16]
    key_payload = fetch_json(f"{key_url}?{urllib.parse.urlencode({'nonce': nonce, 'sign': sign})}", timeout, headers)
    encrypted_key = str(key_payload.get("key") or "")
    if not encrypted_key:
        raise ValueError("视频 key 响应缺少 key")
    key_text = base64.b64decode(encrypted_key)
    decryption_key = decrypt_aes_ecb(key_text, sign.encode("utf-8"))
    if len(decryption_key) != 16:
        raise ValueError(f"视频解密 key 长度异常: {len(decryption_key)} bytes")
    return decryption_key


def download_m3u8(url: str, dest: Path, timeout: int, max_bytes: int, headers: dict[str, str]) -> tuple[int, str | None]:
    playlist_bytes, content_type = read_url_bytes(url, timeout, headers)
    playlist_text = playlist_bytes.decode("utf-8-sig")
    media_url = choose_media_playlist_url(url, playlist_text)
    if media_url != url:
        playlist_bytes, content_type = read_url_bytes(media_url, timeout, headers)
        playlist_text = playlist_bytes.decode("utf-8-sig")

    segments, key_info = media_segment_urls(media_url, playlist_text)
    key_bytes = None
    if key_info:
        key_bytes = fetch_hls_decryption_key(key_info, timeout, headers)
    total = 0
    with dest.open("wb") as fh:
        for segment_url in segments:
            segment, _segment_type = read_url_bytes(segment_url, timeout, headers)
            if key_info and key_bytes is not None:
                segment = decrypt_aes128_segment(segment, key_bytes, key_info["iv"])
            total += len(segment)
            if total > max_bytes:
                raise ValueError(f"文件超过大小限制 {max_bytes} bytes")
            fh.write(segment)
    return total, content_type or "application/vnd.apple.mpegurl"


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
        is_m3u8 = ext == "m3u8" or str(url).lower().split("?", 1)[0].endswith(".m3u8")
        output_ext = "ts" if is_m3u8 else ext
        attempt_dest = downloads_dir / f"{title}_{resource_id}.{output_ext}"
        try:
            if is_m3u8:
                size, content_type = download_m3u8(str(url), attempt_dest, timeout, max_bytes, headers)
                final_ext = "ts"
            else:
                size, content_type = download_url(str(url), attempt_dest, timeout, max_bytes, headers)
                final_ext = extension_for(option, str(url), content_type)
                validate_downloaded_file(attempt_dest, option, output_ext, content_type)
            if final_ext != output_ext:
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
    options = input_options(data)
    if not isinstance(options, list):
        print("error: input must contain options or candidates list", file=sys.stderr)
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
                probed.append(probe_option(option, args.timeout, headers, browser_state=args.browser_state))
            else:
                if args.browser_state:
                    raise ValueError("--browser-state 当前只支持 --probe-only，不用于静默正式下载")
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
        "browser_state_context": bool(args.browser_state),
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
    parser.add_argument("input", help="Selection JSON or candidate JSON file, or '-' for stdin")
    parser.add_argument("--select", required=True, help="Option ids, e.g. 1,2 or all")
    parser.add_argument("--work-dir", default=".learning-resource-work", help="Work cache directory")
    parser.add_argument("-o", "--output", help="Write download JSON to this file")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    parser.add_argument("--max-bytes", type=int, default=200 * 1024 * 1024, help="Maximum file size")
    parser.add_argument("--allow-auth", action="store_true", help="允许使用授权上下文下载 requires_auth 候选")
    parser.add_argument("--probe-only", action="store_true", help="只探测候选 URL 可访问性，不保存文件")
    parser.add_argument("--browser-state", help="可选 Playwright storage state；只在 --probe-only 探测时使用")
    parser.add_argument("--access-token", help="SmartEdu access token; prefer SMARTEDU_ACCESS_TOKEN")
    parser.add_argument("--cookie", help="SmartEdu cookie; prefer SMARTEDU_COOKIE")
    parser.add_argument("--header", action="append", help="额外请求头，格式 'Name: value'；也可用 SMARTEDU_HEADERS")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
