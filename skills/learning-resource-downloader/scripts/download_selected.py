#!/usr/bin/env python3
"""Download selected learning resource options into a work cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
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


def should_skip(option: dict[str, Any]) -> str | None:
    if option.get("requires_auth"):
        return "需要登录或授权访问"
    candidate = option.get("candidate") or {}
    raw = candidate.get("raw") or {}
    warnings = " ".join(str(item) for item in raw.get("warnings") or [])
    if any(term in warnings for term in ["下载器", "破解", "成人"]):
        return "候选存在风险提示"
    return None


def download_url(url: str, dest: Path, timeout: int, max_bytes: int) -> tuple[int, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "learning-resource-agent/0.1"})
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


def download_option(option: dict[str, Any], downloads_dir: Path, timeout: int, max_bytes: int) -> dict[str, Any]:
    candidate = option.get("candidate") or {}
    url = option.get("source_url") or candidate.get("source_url")
    if not url:
        raise ValueError("缺少 source_url")

    parsed = urllib.parse.urlparse(str(url))
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 http/https 下载")

    downloads_dir.mkdir(parents=True, exist_ok=True)
    ext = extension_for(option, str(url))
    title = safe_name(option.get("title") or candidate.get("title") or option.get("option_id"))
    resource_id = safe_name(option.get("resource_id") or candidate.get("resource_id") or option.get("option_id"), limit=24)
    dest = downloads_dir / f"{title}_{resource_id}.{ext}"
    size, content_type = download_url(str(url), dest, timeout, max_bytes)
    final_ext = extension_for(option, str(url), content_type)
    if final_ext != ext:
        final_dest = dest.with_suffix(f".{final_ext}")
        dest.rename(final_dest)
        dest = final_dest
    return {
        "option_id": option.get("option_id"),
        "title": option.get("title"),
        "source_url": str(url),
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

    downloaded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for selected_id in selected_ids:
        option = options_by_id.get(selected_id)
        if not option:
            failures.append({"option_id": selected_id, "title": None, "source_url": None, "error": "选择编号不存在", "candidate": {}})
            continue

        skip_reason = should_skip(option)
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
            downloaded.append(download_option(option, downloads_dir, args.timeout, args.max_bytes))
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

    if downloaded and not skipped and not failures:
        status = "completed"
    elif downloaded:
        status = "partial"
    else:
        status = "failed"

    result = {
        "download_schema": "learning-resource-download/v1",
        "status": status,
        "requested": selected_ids,
        "downloaded_files": downloaded,
        "skipped": skipped,
        "failures": failures,
        "work_dir": str(work_dir),
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if downloaded else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Download selected learning resources into work cache")
    parser.add_argument("input", help="Selection JSON file, or '-' for stdin")
    parser.add_argument("--select", required=True, help="Option ids, e.g. A,B or all")
    parser.add_argument("--work-dir", default=".learning-resource-work", help="Work cache directory")
    parser.add_argument("-o", "--output", help="Write download JSON to this file")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    parser.add_argument("--max-bytes", type=int, default=200 * 1024 * 1024, help="Maximum file size")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
