#!/usr/bin/env python3
"""Convert ranked learning resources into user selection options."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SHOW_LEVELS = {"excellent", "high", "medium"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def option_id(index: int) -> str:
    return str(index + 1)


def compact_summary(candidate: dict[str, Any], reasons: list[str]) -> str:
    parts: list[str] = []
    if candidate.get("official"):
        parts.append("官方来源")
    if candidate.get("stage") or candidate.get("grade"):
        parts.append("适配" + "".join(str(candidate.get(k) or "") for k in ["stage", "grade"]))
    if candidate.get("subject"):
        parts.append(f"学科为{candidate.get('subject')}")
    if candidate.get("version"):
        parts.append(f"版本为{candidate.get('version')}")
    if candidate.get("volume"):
        parts.append(f"册次为{candidate.get('volume')}")
    if not parts and reasons:
        parts.extend(reasons[:2])
    return "，".join(parts) or "候选资源信息较完整，可作为备选查看"


def user_facing_url(candidate: dict[str, Any]) -> str:
    raw = candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {}
    if candidate.get("source") == "smartedu-resources":
        detail_page = raw.get("detail_page")
        if isinstance(detail_page, str) and detail_page.startswith(("http://", "https://")):
            return detail_page
    return candidate.get("source_url")


def make_option(item: dict[str, Any], index: int) -> dict[str, Any]:
    candidate = item.get("candidate") or {}
    reasons = [str(value) for value in as_list(item.get("reasons")) if value]
    warnings = [str(value) for value in as_list(item.get("warnings")) if value]
    display_url = user_facing_url(candidate)
    return {
        "option_id": option_id(index),
        "rank": item.get("rank"),
        "title": candidate.get("title") or "未命名资源",
        "source_name": candidate.get("source_name") or candidate.get("provider") or "",
        "source_url": display_url,
        "download_url": candidate.get("source_url"),
        "resource_id": candidate.get("resource_id"),
        "resource_type": candidate.get("resource_type"),
        "format": candidate.get("format"),
        "quality_level": item.get("quality_level"),
        "score": item.get("final_score"),
        "recommendation": item.get("recommendation"),
        "downloadable": bool(candidate.get("downloadable")),
        "requires_auth": bool(candidate.get("requires_auth")),
        "official": bool(candidate.get("official")),
        "summary": compact_summary(candidate, reasons),
        "reasons": reasons,
        "warnings": warnings,
        "candidate": candidate,
    }


def should_show(item: dict[str, Any], include_low: bool) -> bool:
    level = item.get("quality_level")
    if level in SHOW_LEVELS:
        return True
    return include_low and level == "low"


def render_user_message(options: list[dict[str, Any]], hidden_count: int) -> str:
    if not options:
        return "没有找到足够合适的学习资源。建议补充年龄/年级、主题、资源类型后重新搜索。"

    lines = [f"找到 {len(options)} 个可选学习资源："]
    for option in options:
        auth = "；需要登录或授权访问" if option["requires_auth"] else ""
        downloadable = "可下载" if option["downloadable"] else "可查看页面"
        lines.extend(
            [
                "",
                f"{option['option_id']}. {option['title']}",
                f"   来源：{option['source_name'] or '未知来源'}",
                f"   评分：{option['score']} / {option['quality_level']}",
                f"   格式：{option['format'] or '未知'}，类型：{option['resource_type'] or '未知'}，{downloadable}{auth}",
                f"   摘要：{option['summary']}",
            ]
        )
        if option["warnings"]:
            lines.append(f"   提示：{'；'.join(option['warnings'][:2])}")
    if hidden_count:
        lines.append("")
        lines.append(f"另有 {hidden_count} 个低质量或风险候选已隐藏。")
    lines.append("")
    lines.append("请回复要下载的编号，例如 1、2，或回复“重新搜索”。")
    return "\n".join(lines)


def select_payload(data: dict[str, Any], max_options: int, include_low: bool) -> dict[str, Any]:
    ranked = data.get("ranked_candidates") or []
    rejected = data.get("rejected_candidates") or []
    if not isinstance(ranked, list):
        raise ValueError("ranked_candidates must be a list")

    options: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []

    for item in ranked:
        if should_show(item, include_low) and len(options) < max_options:
            options.append(make_option(item, len(options)))
        else:
            hidden.append(item)
    hidden.extend(rejected)

    status = "awaiting_user_selection" if options else "no_suitable_options"
    message = render_user_message(options, len(hidden))
    return {
        "selection_schema": "learning-resource-selection/v1",
        "status": status,
        "total_ranked": len(ranked) + len(rejected),
        "shown_count": len(options),
        "hidden_count": len(hidden),
        "options": options,
        "hidden_options": hidden,
        "user_message": message,
        "next_action": "请用户选择要下载的资源编号" if options else "重新澄清需求或换来源搜索",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build user selection options from ranking JSON")
    parser.add_argument("input", help="Ranking JSON file, or '-' for stdin")
    parser.add_argument("-o", "--output", help="Write selection JSON to this file")
    parser.add_argument("--max-options", type=int, default=5, help="Maximum visible options")
    parser.add_argument("--include-low", action="store_true", help="Also show low quality options")
    args = parser.parse_args()

    try:
        result = select_payload(load_json(args.input), args.max_options, args.include_low)
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
