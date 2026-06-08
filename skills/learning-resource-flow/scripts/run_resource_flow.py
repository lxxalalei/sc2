#!/usr/bin/env python3
"""Run source-first learning resource candidate flow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def norm(value: Any) -> str:
    return str(value or "").strip()


def run_json_command(cmd: list[str], cwd: Path) -> tuple[int, dict[str, Any], str]:
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    stdout = result.stdout.strip()
    payload: dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}
    return result.returncode, payload, result.stderr.strip()


def run_command(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)


def first_task(intent: dict[str, Any]) -> dict[str, Any]:
    tasks = intent.get("execution_tasks") or []
    if isinstance(tasks, list) and tasks:
        return next((item for item in tasks if isinstance(item, dict)), {})
    return {}


def intent_filters(intent: dict[str, Any]) -> dict[str, Any]:
    task = first_task(intent)
    filters = dict(task.get("filters") or {})
    for key in [
        "learner_age",
        "stage",
        "grade",
        "learning_domain",
        "subject",
        "core_topic",
        "resource_goal",
        "resource_types",
        "format_preferences",
        "version",
        "volume",
    ]:
        if intent.get(key) not in (None, "", []):
            filters.setdefault(key, intent[key])
    return filters


def build_query(intent: dict[str, Any]) -> str:
    task = first_task(intent)
    if task.get("query"):
        return norm(task["query"])
    if intent.get("normalized_query"):
        return norm(intent["normalized_query"])
    filters = intent_filters(intent)
    parts: list[str] = []
    for key in ["learner_age", "stage", "grade", "subject", "learning_domain", "core_topic"]:
        value = filters.get(key)
        if value:
            parts.append(f"{value}岁" if key == "learner_age" and str(value).isdigit() else str(value))
    parts.extend(str(item) for item in as_list(filters.get("resource_types")))
    parts.extend(str(item) for item in as_list(filters.get("format_preferences")))
    return " ".join(dict.fromkeys(part for part in parts if part))


def wants_textbook(intent: dict[str, Any]) -> bool:
    values = as_list(intent.get("resource_types")) + as_list(intent_filters(intent).get("resource_types"))
    blob = " ".join(str(item) for item in values) + " " + build_query(intent)
    return any(term in blob for term in ["教材", "课本", "教科书", "电子教材"])


def source_summary(source_name: str, status: str, payload: dict[str, Any], error: str = "") -> dict[str, Any]:
    candidates = payload.get("candidates") or []
    return {
        "source": source_name,
        "status": status,
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "summary": payload.get("summary") or {},
        "error": error,
    }


def local_candidates(
    intent: dict[str, Any],
    args: argparse.Namespace,
    skills_dir: Path,
    package_root: Path,
    work_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    index_file = Path(args.local_index_file)
    if not index_file.is_absolute():
        index_file = package_root / index_file

    if not index_file.exists():
        return [], [
            {
                "source": "local-library-search",
                "status": "index_missing",
                "candidate_count": 0,
                "summary": {"index_file": str(index_file)},
                "error": "",
            }
        ], {}

    task_json = work_dir / "local-task.json"
    output_json = work_dir / "local-candidates.json"
    write_json(task_json, {"filters": intent_filters(intent), "intent": intent, "query": build_query(intent)})

    script = skills_dir / "local-library-search" / "scripts" / "search_local_library.py"
    cmd = [
        sys.executable,
        str(script),
        "--query",
        build_query(intent),
        "--task-json",
        str(task_json),
        "--index-file",
        str(index_file),
        "--limit",
        str(args.local_limit),
        "--min-score",
        str(args.local_min_score),
        "-o",
        str(output_json),
    ]
    code, payload, error = run_json_command(cmd, package_root)
    if not payload and output_json.exists():
        payload = load_json(str(output_json))
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    return candidates, [source_summary("local-library-search", "ok" if code == 0 else "failed", payload, error)], {
        "local_candidates": str(output_json)
    }


def step_summary(source_name: str, status: str, payload: dict[str, Any], error: str = "") -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
    return {
        "source": source_name,
        "status": status,
        "candidate_count": len(candidates),
        "source_count": len(sources),
        "profile_count": len(profiles),
        "summary": summary,
        "error": error,
    }


def smartedu_candidates(
    intent: dict[str, Any],
    args: argparse.Namespace,
    skills_dir: Path,
    package_root: Path,
    work_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    script = skills_dir / "smartedu-resources" / "scripts" / "smartedu_resources.py"
    filters = intent_filters(intent)
    query = build_query(intent)
    sources: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    profile_cmd = [
        sys.executable,
        str(script),
        "site-profile",
        "--library-list-json",
        str(skills_dir / "smartedu-resources" / "references" / "sample-librarylist.json"),
    ]
    code, profile_payload, profile_error = run_json_command(profile_cmd, package_root)
    sources.append(source_summary("smartedu-resources:site-profile", "ok" if code == 0 else "failed", profile_payload, profile_error))

    if wants_textbook(intent):
        cmd = [
            sys.executable,
            str(script),
            "textbook-candidates",
            "--show",
            str(args.per_source_limit),
            "--work-dir",
            str(work_dir / "smartedu-textbooks"),
        ]
        for flag, key in [
            ("--stage", "stage"),
            ("--grade", "grade"),
            ("--subject", "subject"),
            ("--version", "version"),
            ("--volume", "volume"),
        ]:
            if filters.get(key):
                cmd.extend([flag, str(filters[key])])
        if query:
            cmd.extend(["--query", query])
    else:
        cmd = [
            sys.executable,
            str(script),
            "search-resources",
            "--query",
            query,
            "--limit",
            str(args.per_source_limit),
        ]
        if args.smartedu_search_response_json:
            cmd.extend(["--search-response-json", args.smartedu_search_response_json])
        if args.smartedu_fetch_details:
            cmd.append("--fetch-details")
        if args.smartedu_detail_dir:
            cmd.extend(["--detail-dir", args.smartedu_detail_dir])
        if args.smartedu_offline_details_only:
            cmd.append("--offline-details-only")

    code, payload, error = run_json_command(cmd, package_root)
    status = "ok" if code == 0 else "no_candidates"
    if payload.get("candidates"):
        candidates.extend(payload["candidates"])
    sources.append(source_summary("smartedu-resources", status, payload, error))
    return candidates, sources


def web_candidates(
    intent: dict[str, Any],
    args: argparse.Namespace,
    skills_dir: Path,
    package_root: Path,
    work_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    if not args.web_search_results_json:
        return [], [
            {
                "source": "web-learning-search",
                "status": "waiting_for_agent_search_results",
                "candidate_count": 0,
                "suggested_query": build_query(intent),
                "error": "",
            }
        ], {}
    script = skills_dir / "web-learning-search" / "scripts" / "search_web_resources.py"
    cmd = [
        sys.executable,
        str(script),
        "--query",
        build_query(intent),
        "--search-results-json",
        args.web_search_results_json,
        "--limit",
        str(args.web_limit),
    ]
    code, payload, error = run_json_command(cmd, package_root)
    status = "ok" if code == 0 else "failed"
    candidates = payload.get("candidates") or []
    web_items = candidates if isinstance(candidates, list) else []
    source_runs = [source_summary("web-learning-search", status, payload, error)]
    work_files: dict[str, str] = {}

    web_candidates_json = work_dir / "web-candidates.json"
    write_json(web_candidates_json, payload or {"candidates": web_items})
    work_files["web_candidates"] = str(web_candidates_json)

    discovery_script = skills_dir / "resource-source-discovery" / "scripts" / "discover_sources.py"
    discovery_json = work_dir / "source-discovery.json"
    code, discovery_payload, discovery_error = run_json_command(
        [sys.executable, str(discovery_script), str(web_candidates_json), "--limit", str(args.source_discovery_limit)],
        package_root,
    )
    if discovery_payload:
        write_json(discovery_json, discovery_payload)
        work_files["source_discovery"] = str(discovery_json)
    source_runs.append(step_summary("resource-source-discovery", "ok" if discovery_payload.get("sources") else "no_sources", discovery_payload, discovery_error))

    generic_items: list[dict[str, Any]] = []
    if discovery_payload.get("sources"):
        profiler_script = skills_dir / "web-resource-profiler" / "scripts" / "profile_site.py"
        profile_json = work_dir / "site-profile.json"
        profile_cmd = [
            sys.executable,
            str(profiler_script),
            "--discovery-json",
            str(discovery_json),
            "--limit",
            str(args.profile_limit),
            "--timeout",
            str(args.profile_timeout),
        ]
        if args.web_profile_html_file:
            profile_cmd.extend(["--html-file", args.web_profile_html_file])
        code, profile_payload, profile_error = run_json_command(profile_cmd, package_root)
        if profile_payload:
            write_json(profile_json, profile_payload)
            work_files["site_profile"] = str(profile_json)
        source_runs.append(step_summary("web-resource-profiler", "ok" if profile_payload.get("profiles") else "no_profiles", profile_payload, profile_error))

        if profile_payload.get("profiles"):
            task_json = work_dir / "generic-task.json"
            write_json(task_json, {"filters": intent_filters(intent), "intent": intent})
            generic_script = skills_dir / "generic-web-source" / "scripts" / "extract_candidates.py"
            generic_json = work_dir / "generic-candidates.json"
            generic_cmd = [
                sys.executable,
                str(generic_script),
                "--site-profile-json",
                str(profile_json),
                "--task-json",
                str(task_json),
                "--query",
                build_query(intent),
                "--limit",
                str(args.generic_limit),
            ]
            if args.generic_include_non_generic:
                generic_cmd.append("--include-non-generic")
            code, generic_payload, generic_error = run_json_command(generic_cmd, package_root)
            if generic_payload:
                write_json(generic_json, generic_payload)
                work_files["generic_candidates"] = str(generic_json)
            raw_generic = generic_payload.get("candidates") or []
            if isinstance(raw_generic, list):
                generic_items = raw_generic
            source_runs.append(source_summary("generic-web-source", "ok" if generic_items else "no_candidates", generic_payload, generic_error))

    return web_items + generic_items, source_runs, work_files


def run_download_archive_chain(
    selection_json: Path,
    args: argparse.Namespace,
    skills_dir: Path,
    package_root: Path,
    work_dir: Path,
) -> dict[str, Any]:
    download_json = work_dir / "download-result.json"
    organize_json = work_dir / "organize-result.json"
    index_update_json = work_dir / "index-update-result.json"

    downloader = skills_dir / "learning-resource-downloader" / "scripts" / "download_selected.py"
    download_cmd = [
        sys.executable,
        str(downloader),
        str(selection_json),
        "--select",
        args.select,
        "--work-dir",
        str(work_dir / "download-cache"),
        "--timeout",
        str(args.download_timeout),
        "--max-bytes",
        str(args.max_download_bytes),
        "-o",
        str(download_json),
    ]
    if args.allow_auth:
        download_cmd.append("--allow-auth")
    if args.probe_only:
        download_cmd.append("--probe-only")
    for header in args.header or []:
        download_cmd.extend(["--header", header])
    if args.access_token:
        download_cmd.extend(["--access-token", args.access_token])
    if args.cookie:
        download_cmd.extend(["--cookie", args.cookie])

    download_code, download_payload, download_error = run_json_command(download_cmd, package_root)
    if not download_payload and download_json.exists():
        download_payload = load_json(str(download_json))

    result = {
        "download": {
            "status": download_payload.get("status") or ("failed" if download_code else "completed"),
            "output_file": str(download_json),
            "error": download_error,
            "summary": {
                "downloaded": len(download_payload.get("downloaded_files") or []),
                "probed": len(download_payload.get("probed") or []),
                "skipped": len(download_payload.get("skipped") or []),
                "failed": len(download_payload.get("failures") or []),
            },
        }
    }

    if args.probe_only or not download_payload.get("downloaded_files"):
        return result

    analyzed_download_payload, analyzed_download_file, analysis_error = analyze_downloaded_files(
        download_payload, skills_dir, package_root, work_dir
    )
    organize_input_json = download_json
    if analyzed_download_payload:
        organize_input_json = analyzed_download_file
        result["download"]["analyzed_output_file"] = str(analyzed_download_file)
        result["download"]["analysis_error"] = analysis_error
        result["download"]["post_download_analysis"] = analyzed_download_payload.get("post_download_analysis") or {}
        write_json(analyzed_download_file, analyzed_download_payload)

    organizer = skills_dir / "learning-library-organizer" / "scripts" / "organize_downloads.py"
    organize_cmd = [
        sys.executable,
        str(organizer),
        str(organize_input_json),
        "--library-dir",
        args.library_dir,
        "--work-dir",
        str(work_dir),
        "--mode",
        args.organize_mode,
        "--review-threshold",
        str(args.review_threshold),
        "-o",
        str(organize_json),
    ]
    if args.organize_dry_run:
        organize_cmd.append("--dry-run")
    organize_code, organize_payload, organize_error = run_json_command(organize_cmd, package_root)
    if not organize_payload and organize_json.exists():
        organize_payload = load_json(str(organize_json))
    result["organize"] = {
        "status": organize_payload.get("status") or ("failed" if organize_code else "completed"),
        "output_file": str(organize_json),
        "error": organize_error,
        "summary": organize_payload.get("summary") or {},
    }

    if not organize_payload.get("organized_files"):
        return result

    indexer = skills_dir / "learning-library-index" / "scripts" / "update_index.py"
    index_cmd = [
        sys.executable,
        str(indexer),
        str(organize_json),
        "--index-dir",
        args.index_dir,
        "--library-dir",
        args.library_dir,
        "-o",
        str(index_update_json),
    ]
    if args.index_dry_run:
        index_cmd.append("--dry-run")
    index_code, index_payload, index_error = run_json_command(index_cmd, package_root)
    if not index_payload and index_update_json.exists():
        index_payload = load_json(str(index_update_json))
    result["index"] = {
        "status": index_payload.get("status") or ("failed" if index_code else "completed"),
        "output_file": str(index_update_json),
        "error": index_error,
        "summary": index_payload.get("summary") or {},
    }
    return result


def candidate_from_download(item: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(item.get("candidate") if isinstance(item.get("candidate"), dict) else {})
    raw = dict(candidate.get("raw") if isinstance(candidate.get("raw"), dict) else {})
    raw["download"] = {key: value for key, value in item.items() if key != "candidate"}
    candidate.update(
        {
            "option_id": item.get("option_id"),
            "title": item.get("title") or candidate.get("title"),
            "source_url": item.get("source_url") or candidate.get("source_url"),
            "local_file": item.get("local_file"),
            "format": item.get("format") or candidate.get("format"),
            "resource_type": item.get("resource_type") or candidate.get("resource_type"),
            "size": item.get("size") or candidate.get("size"),
            "sha256": item.get("sha256"),
            "raw": raw,
        }
    )
    return candidate


def analyze_downloaded_files(
    download_payload: dict[str, Any],
    skills_dir: Path,
    package_root: Path,
    work_dir: Path,
) -> tuple[dict[str, Any] | None, Path, str]:
    downloaded_files = download_payload.get("downloaded_files") if isinstance(download_payload.get("downloaded_files"), list) else []
    analyzed_download_file = work_dir / "download-result.analyzed.json"
    if not downloaded_files:
        return None, analyzed_download_file, ""

    candidates_json = work_dir / "downloaded-candidates.json"
    analysis_json = work_dir / "downloaded-analysis.json"
    write_json(
        candidates_json,
        {
            "candidate_schema": "learning-resource-candidate/v1",
            "candidates": [candidate_from_download(item) for item in downloaded_files if isinstance(item, dict)],
        },
    )
    analyzer = skills_dir / "learning-resource-analyzer" / "scripts" / "analyze_candidates.py"
    code, analysis_payload, analysis_error = run_json_command(
        [sys.executable, str(analyzer), str(candidates_json), "-o", str(analysis_json)],
        package_root,
    )
    if not analysis_payload and analysis_json.exists():
        analysis_payload = load_json(str(analysis_json))
    analyzed_candidates = analysis_payload.get("candidates") if isinstance(analysis_payload.get("candidates"), list) else []
    if code != 0 or not analyzed_candidates:
        return None, analyzed_download_file, analysis_error

    by_local_file = {str(item.get("local_file") or ""): item for item in analyzed_candidates if isinstance(item, dict)}
    updated_files: list[dict[str, Any]] = []
    for item in downloaded_files:
        if not isinstance(item, dict):
            continue
        local_file = str(item.get("local_file") or "")
        analyzed = by_local_file.get(local_file)
        if not analyzed:
            updated_files.append(item)
            continue
        updated = dict(item)
        updated["format"] = analyzed.get("format") or item.get("format")
        updated["candidate"] = analyzed
        updated_files.append(updated)

    analyzed_download = dict(download_payload)
    analyzed_download["downloaded_files"] = updated_files
    analyzed_download["post_download_analysis"] = {
        "status": "completed",
        "candidates_file": str(candidates_json),
        "analysis_file": str(analysis_json),
        "analyzed_count": len(analyzed_candidates),
    }
    return analyzed_download, analyzed_download_file, analysis_error


def post_selection_status(post_selection: dict[str, Any]) -> str:
    download_status = (post_selection.get("download") or {}).get("status")
    organize_status = (post_selection.get("organize") or {}).get("status")
    index_status = (post_selection.get("index") or {}).get("status")
    if download_status in {"failed", None}:
        return "post_selection_failed"
    if download_status in {"partial"} or organize_status in {"partial", "failed"} or index_status in {"partial", "failed"}:
        return "post_selection_partial"
    if download_status == "completed" and not organize_status and not index_status:
        return "post_selection_probed" if (post_selection.get("download") or {}).get("summary", {}).get("probed") else "post_selection_downloaded"
    return "post_selection_completed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run source-first learning resource flow")
    parser.add_argument("--intent-json", required=True, help="learning-resource-intent/v1 JSON")
    parser.add_argument("--work-dir", default=".learning-resource-flow-work/resource-flow", help="工作目录")
    parser.add_argument("--min-source-candidates", type=int, default=3, help="已优化站点候选少于该数量时触发网络搜索分支")
    parser.add_argument("--per-source-limit", type=int, default=8, help="每个已优化 source 最多候选数")
    parser.add_argument("--web-limit", type=int, default=10, help="通用搜索候选上限")
    parser.add_argument("--web-search-results-json", help="agent 通用搜索结果 JSON；未提供时只输出需要搜索的状态")
    parser.add_argument("--source-discovery-limit", type=int, default=10, help="web fallback 阶段最多发现多少个来源")
    parser.add_argument("--profile-limit", type=int, default=5, help="web fallback 阶段最多分析多少个未知资源站")
    parser.add_argument("--profile-timeout", type=int, default=8, help="资源站结构分析 HTTP 超时秒数")
    parser.add_argument("--web-profile-html-file", help="离线调试时给 profiler 使用的本地 HTML 样例")
    parser.add_argument("--generic-limit", type=int, default=20, help="generic-web-source 最多处理多少个 profile")
    parser.add_argument("--generic-include-non-generic", action="store_true", help="也从非 generic_extract profile 中抽取直链")
    parser.add_argument("--skip-local-search", action="store_true", help="跳过本地资料库外部索引检索")
    parser.add_argument("--always-search-sources", action="store_true", help="即使本地候选数量足够，也继续查询外部来源")
    parser.add_argument("--local-index-file", default=".learning-resource-work/index/resources.json", help="本地资料库外部索引 resources.json")
    parser.add_argument("--local-limit", type=int, default=10, help="本地资料库候选上限")
    parser.add_argument("--local-min-score", type=float, default=8.0, help="本地资料库检索最低匹配分")
    parser.add_argument("--local-satisfy-candidates", type=int, default=3, help="本地候选达到该数量时默认不继续外部搜索")
    parser.add_argument("--smartedu-search-response-json", help="离线 SmartEdu 搜索响应 JSON")
    parser.add_argument("--smartedu-fetch-details", action="store_true", help="SmartEdu 搜索后继续追踪详情")
    parser.add_argument("--smartedu-detail-dir", help="SmartEdu 详情 JSON 目录")
    parser.add_argument("--smartedu-offline-details-only", action="store_true", help="SmartEdu 详情只从本地目录读取")
    parser.add_argument("--select", help="用户确认下载的候选编号，例如 A,B 或 all；未提供时只输出候选清单")
    parser.add_argument("--library-dir", default="学习资料库", help="最终学习资料库目录")
    parser.add_argument("--index-dir", default=".learning-resource-work/index", help="资料库外部索引目录")
    parser.add_argument("--organize-mode", choices=["copy", "move"], default="copy", help="下载后入库方式")
    parser.add_argument("--review-threshold", type=float, default=0.55, help="自动归档分类置信度阈值")
    parser.add_argument("--organize-dry-run", action="store_true", help="只预览归档，不写入最终资料库")
    parser.add_argument("--index-dry-run", action="store_true", help="只预览索引更新，不写入索引文件")
    parser.add_argument("--probe-only", action="store_true", help="用户选择后只探测可访问性，不下载")
    parser.add_argument("--download-timeout", type=int, default=20, help="下载 HTTP 超时秒数")
    parser.add_argument("--max-download-bytes", type=int, default=200 * 1024 * 1024, help="单个下载文件大小上限")
    parser.add_argument("--allow-auth", action="store_true", help="允许使用授权上下文下载 requires_auth 候选")
    parser.add_argument("--access-token", help="SmartEdu access token；优先使用环境变量")
    parser.add_argument("--cookie", help="SmartEdu cookie；优先使用环境变量")
    parser.add_argument("--header", action="append", help="下载阶段额外请求头，格式 'Name: value'")
    parser.add_argument("-o", "--output", help="写入最终 selection JSON")
    args = parser.parse_args()

    intent = load_json(args.intent_json)
    if intent.get("status") == "needs_clarification":
        result = {
            "flow_schema": "learning-resource-flow/v1",
            "status": "needs_clarification",
            "clarifying_questions": intent.get("clarifying_questions") or [],
            "intent": intent,
        }
        if args.output:
            write_json(Path(args.output), result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    script_path = Path(__file__).resolve()
    skills_dir = script_path.parents[2]
    package_root = skills_dir.parent
    work_dir = Path(args.work_dir)
    if not work_dir.is_absolute():
        work_dir = package_root / work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    local_items: list[dict[str, Any]] = []
    local_runs: list[dict[str, Any]] = []
    local_work_files: dict[str, str] = {}
    if not args.skip_local_search:
        local_items, local_runs, local_work_files = local_candidates(intent, args, skills_dir, package_root, work_dir)

    all_candidates = list(local_items)
    source_runs = list(local_runs)
    should_query_optimized = (
        args.always_search_sources
        or len(local_items) < args.local_satisfy_candidates
        or len(local_items) < args.min_source_candidates
    )
    optimized_candidates: list[dict[str, Any]] = []
    if should_query_optimized:
        optimized_candidates, optimized_runs = smartedu_candidates(intent, args, skills_dir, package_root, work_dir)
        all_candidates.extend(optimized_candidates)
        source_runs.extend(optimized_runs)
    used_web = False
    needs_web_search = False
    web_work_files: dict[str, str] = {}
    if len(all_candidates) < args.min_source_candidates:
        used_web = True
        web_items, web_runs, web_work_files = web_candidates(intent, args, skills_dir, package_root, work_dir)
        all_candidates.extend(web_items)
        source_runs.extend(web_runs)
        needs_web_search = bool(web_runs and web_runs[0].get("status") == "waiting_for_agent_search_results")

    merged_json = work_dir / "merged-candidates.json"
    analyzed_json = work_dir / "analyzed.json"
    ranking_json = work_dir / "ranking.json"
    selection_json = Path(args.output) if args.output else work_dir / "selection.json"
    work_files = {
        "merged_candidates": str(merged_json),
        "analyzed": str(analyzed_json),
        "ranking": str(ranking_json),
    }
    work_files.update(local_work_files)
    work_files.update(web_work_files)
    merged = {
        "candidate_schema": "learning-resource-candidate/v1",
        "flow_schema": "learning-resource-flow/v1",
        "query": build_query(intent),
        "filters": intent_filters(intent),
        "intent": intent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_first": True,
        "local_first": not args.skip_local_search,
        "used_local_candidates": bool(local_items),
        "used_web_fallback": used_web,
        "needs_web_search": needs_web_search,
        "source_runs": source_runs,
        "work_files": work_files,
        "candidates": all_candidates,
    }
    write_json(merged_json, merged)

    if not all_candidates:
        result = dict(merged)
        result["status"] = "needs_web_search" if needs_web_search else "no_candidates"
        result["next_action"] = "请 agent 使用通用搜索能力获取搜索结果，再用 --web-search-results-json 继续流程。"
        write_json(selection_json, result)
        if not args.output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    analyzer = skills_dir / "learning-resource-analyzer" / "scripts" / "analyze_candidates.py"
    ranker = skills_dir / "learning-resource-ranker" / "scripts" / "rank_candidates.py"
    selector = skills_dir / "learning-resource-selector" / "scripts" / "select_candidates.py"
    run_command([sys.executable, str(analyzer), str(merged_json), "-o", str(analyzed_json)], package_root)
    run_command([sys.executable, str(ranker), str(analyzed_json), "-o", str(ranking_json)], package_root)
    run_command([sys.executable, str(selector), str(ranking_json), "-o", str(selection_json)], package_root)
    selection = load_json(str(selection_json))
    selection["flow_schema"] = "learning-resource-flow/v1"
    selection["source_first"] = True
    selection["local_first"] = not args.skip_local_search
    selection["used_local_candidates"] = bool(local_items)
    selection["used_web_fallback"] = used_web
    selection["needs_web_search"] = needs_web_search
    selection["source_runs"] = source_runs
    selection["work_files"] = work_files
    if args.select:
        archive_result = run_download_archive_chain(selection_json, args, skills_dir, package_root, work_dir)
        selection["post_selection"] = archive_result
        for key in ["download", "organize", "index"]:
            output_file = (archive_result.get(key) or {}).get("output_file")
            if output_file:
                selection["work_files"][key] = output_file
        selection["status"] = post_selection_status(archive_result)
    write_json(selection_json, selection)
    if not args.output:
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
