#!/usr/bin/env python3
"""Analyze learning resource candidates with lightweight local metadata extraction."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


RISK_TERMS = ["下载器", "高速下载", "破解", "破解版", "成人", "博彩", "贷款", "注册机", "付费", "会员", "登录"]
DOCUMENT_FORMATS = {"pdf", "doc", "docx", "ppt", "pptx", "txt"}
IMAGE_FORMATS = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
AUDIO_FORMATS = {"mp3", "wav", "m4a", "aac", "flac"}
VIDEO_FORMATS = {"mp4", "mov", "avi", "mkv", "webm"}


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)


def norm(value: Any) -> str:
    return str(value or "").strip()


def clean_text(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def detect_format(candidate: dict[str, Any], path: Path | None = None) -> str:
    fmt = norm(candidate.get("format")).lower()
    if fmt:
        return fmt
    source = norm(candidate.get("source_url") or candidate.get("local_file") or candidate.get("file_path"))
    suffix = (path.suffix if path else Path(urllib.parse.urlparse(source).path).suffix).lower().lstrip(".")
    if suffix in {"htm"}:
        return "html"
    return suffix or "unknown"


def analysis_type(fmt: str) -> str:
    if fmt in DOCUMENT_FORMATS:
        return "document"
    if fmt in {"html", "webpage"}:
        return "webpage"
    if fmt in IMAGE_FORMATS or fmt == "image":
        return "image"
    if fmt in AUDIO_FORMATS or fmt == "audio":
        return "audio"
    if fmt in VIDEO_FORMATS or fmt == "video":
        return "video"
    return "unknown"


def risk_warnings(text: str) -> list[str]:
    return [f"包含风险词：{term}" for term in RISK_TERMS if term in text]


def local_path(candidate: dict[str, Any]) -> Path | None:
    value = candidate.get("local_file") or candidate.get("file_path")
    if not value:
        return None
    return Path(str(value))


def fetch_remote_head(candidate: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = norm(candidate.get("source_url"))
    if not url:
        return {}
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "learning-resource-agent/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return {
            "content_type": response.headers.get("Content-Type"),
            "content_length": int(response.headers.get("Content-Length") or 0) or None,
        }


def analyze_html_text(text: str) -> dict[str, Any]:
    parser = TextHTMLParser()
    parser.feed(text)
    full_text = clean_text(" ".join(parser.text_parts), limit=2000)
    title = clean_text(" ".join(parser.title_parts), limit=120)
    return {
        "title": title,
        "text_sample": clean_text(full_text),
        "signals": {"text_length": len(full_text)},
        "confidence": 0.85 if full_text else 0.35,
    }


def analyze_text_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "text_sample": clean_text(text),
        "signals": {"text_length": len(text)},
        "confidence": 0.8 if text.strip() else 0.3,
    }


def extract_zip_xml_text(path: Path, suffix: str) -> dict[str, Any]:
    text_parts: list[str] = []
    slide_count = 0
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if suffix == "docx" and name.startswith("word/") and name.endswith(".xml"):
                raw = archive.read(name).decode("utf-8", errors="ignore")
                text_parts.extend(re.findall(r"<w:t[^>]*>(.*?)</w:t>", raw))
            elif suffix == "pptx" and name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                slide_count += 1
                raw = archive.read(name).decode("utf-8", errors="ignore")
                text_parts.extend(re.findall(r"<a:t>(.*?)</a:t>", raw))
    text = clean_text(" ".join(text_parts), limit=2000)
    return {
        "text_sample": text,
        "signals": {
            "text_length": len(text),
            "slide_count": slide_count if suffix == "pptx" else None,
        },
        "confidence": 0.85 if text else 0.45,
    }


def count_pdf_pages(path: Path) -> int | None:
    data = path.read_bytes()
    count = len(re.findall(rb"/Type\s*/Page\b", data))
    return count or None


def analyze_pdf(path: Path) -> dict[str, Any]:
    page_count = count_pdf_pages(path)
    return {
        "text_sample": "",
        "signals": {
            "file_size": path.stat().st_size,
            "page_count": page_count,
            "text_length": 0,
        },
        "warnings": [] if page_count else ["无法解析 PDF 页数或文本"],
        "confidence": 0.65 if page_count else 0.45,
    }


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            return image.size
    except Exception:
        pass
    try:
        data = path.read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            if len(data) >= 10:
                return struct.unpack("<HH", data[6:10])
        if data.startswith(b"\xff\xd8"):
            index = 2
            while index + 9 < len(data):
                if data[index] != 0xFF:
                    index += 1
                    continue
                marker = data[index + 1]
                block_length = int.from_bytes(data[index + 2 : index + 4], "big")
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                    height = int.from_bytes(data[index + 5 : index + 7], "big")
                    width = int.from_bytes(data[index + 7 : index + 9], "big")
                    return width, height
                index += 2 + block_length
    except Exception:
        return None, None
    return None, None


def ffprobe(path: Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def analyze_local_file(path: Path, fmt: str) -> dict[str, Any]:
    signals: dict[str, Any] = {"file_size": path.stat().st_size}
    warnings: list[str] = []
    if path.stat().st_size < 512 and fmt not in {"html", "txt"}:
        warnings.append("文件过小，可能不是完整资源")

    if fmt == "html":
        html_result = analyze_html_text(path.read_text(encoding="utf-8", errors="replace"))
        html_result["signals"].update(signals)
        html_result["warnings"] = warnings
        return html_result
    if fmt == "txt":
        text_result = analyze_text_file(path)
        text_result["signals"].update(signals)
        text_result["warnings"] = warnings
        return text_result
    if fmt in {"docx", "pptx"}:
        doc_result = extract_zip_xml_text(path, fmt)
        doc_result["signals"].update(signals)
        doc_result["warnings"] = warnings if doc_result["text_sample"] else warnings + ["无法解析文本"]
        return doc_result
    if fmt == "pdf":
        pdf_result = analyze_pdf(path)
        pdf_result["warnings"] = warnings + pdf_result.get("warnings", [])
        return pdf_result
    if fmt in IMAGE_FORMATS or fmt == "image":
        width, height = image_size(path)
        signals.update({"width": width, "height": height})
        return {"text_sample": "", "signals": signals, "warnings": warnings, "confidence": 0.75 if width else 0.5}
    if fmt in AUDIO_FORMATS or fmt in VIDEO_FORMATS or fmt in {"audio", "video"}:
        probe = ffprobe(path)
        duration = None
        if probe.get("format", {}).get("duration"):
            duration = float(probe["format"]["duration"])
        signals["duration_seconds"] = duration
        if fmt in VIDEO_FORMATS or fmt == "video":
            video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
            signals["width"] = video_stream.get("width")
            signals["height"] = video_stream.get("height")
        return {"text_sample": "", "signals": signals, "warnings": warnings, "confidence": 0.75 if probe else 0.45}
    return {"text_sample": "", "signals": signals, "warnings": warnings + ["暂不支持该格式的深度分析"], "confidence": 0.35}


def keywords_from_text(text: str) -> list[str]:
    terms = ["数学", "四则", "运算", "练习", "可打印", "恐龙", "百科", "唐诗", "宋词", "儿歌", "视频", "音频", "课件", "识字"]
    return [term for term in terms if term in text]


def analyze_candidate(candidate: dict[str, Any], fetch_remote: bool, timeout: int) -> dict[str, Any]:
    enriched = dict(candidate)
    raw = dict(enriched.get("raw") or {})
    warnings: list[str] = list(raw.get("warnings") or [])
    path = local_path(candidate)
    fmt = detect_format(candidate, path)
    kind = analysis_type(fmt)
    title_desc = " ".join([norm(candidate.get("title")), norm(candidate.get("description")), norm(candidate.get("source_url"))])

    analysis: dict[str, Any] = {
        "analyzed": True,
        "analysis_type": kind,
        "detected_format": fmt,
        "signals": {},
        "text_sample": "",
        "keywords": [],
        "warnings": [],
        "analysis_confidence": 0.25,
    }

    if path:
        if path.exists():
            try:
                result = analyze_local_file(path, fmt)
                analysis["signals"].update(result.get("signals") or {})
                analysis["text_sample"] = result.get("text_sample") or ""
                warnings.extend(result.get("warnings") or [])
                analysis["analysis_confidence"] = result.get("confidence", analysis["analysis_confidence"])
                if result.get("title") and not enriched.get("title"):
                    enriched["title"] = result["title"]
            except Exception as exc:
                warnings.append(f"本地文件分析失败：{exc}")
        else:
            warnings.append("文件不存在")
    elif fetch_remote:
        try:
            head = fetch_remote_head(candidate, timeout)
            analysis["signals"].update({k: v for k, v in head.items() if v is not None})
            analysis["analysis_confidence"] = 0.5 if head else 0.3
        except Exception as exc:
            warnings.append(f"远程抓取失败：{exc}")
    else:
        warnings.append("远程抓取未启用")

    combined_text = " ".join([title_desc, analysis.get("text_sample") or ""])
    warnings.extend(risk_warnings(combined_text))
    analysis["keywords"] = keywords_from_text(combined_text)
    analysis["warnings"] = list(dict.fromkeys(warnings))
    raw["analysis"] = analysis
    enriched["raw"] = raw
    return enriched


def load_payload(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def analyze_payload(data: dict[str, Any], fetch_remote: bool, timeout: int) -> dict[str, Any]:
    candidates = data.get("candidates") or []
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    analyzed = [analyze_candidate(candidate, fetch_remote, timeout) for candidate in candidates]
    return {
        "analysis_schema": "learning-resource-analysis/v1",
        "candidate_schema": data.get("candidate_schema", "learning-resource-candidate/v1"),
        "source_candidate_count": len(candidates),
        "analyzed_count": len(analyzed),
        "query": data.get("query"),
        "filters": data.get("filters"),
        "candidates": analyzed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze learning resource candidates")
    parser.add_argument("input", help="Candidate JSON file, or '-' for stdin")
    parser.add_argument("-o", "--output", help="Write analysis JSON to this file")
    parser.add_argument("--fetch-remote", action="store_true", help="Fetch remote headers for candidates without local files")
    parser.add_argument("--timeout", type=int, default=10, help="Remote request timeout seconds")
    args = parser.parse_args()

    try:
        result = analyze_payload(load_payload(args.input), args.fetch_remote, args.timeout)
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
