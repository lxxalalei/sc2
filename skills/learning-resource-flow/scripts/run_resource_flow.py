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
    parser.add_argument("--smartedu-search-response-json", help="离线 SmartEdu 搜索响应 JSON")
    parser.add_argument("--smartedu-fetch-details", action="store_true", help="SmartEdu 搜索后继续追踪详情")
    parser.add_argument("--smartedu-detail-dir", help="SmartEdu 详情 JSON 目录")
    parser.add_argument("--smartedu-offline-details-only", action="store_true", help="SmartEdu 详情只从本地目录读取")
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

    optimized_candidates, source_runs = smartedu_candidates(intent, args, skills_dir, package_root, work_dir)
    all_candidates = list(optimized_candidates)
    used_web = False
    needs_web_search = False
    web_work_files: dict[str, str] = {}
    if len(optimized_candidates) < args.min_source_candidates:
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
    work_files.update(web_work_files)
    merged = {
        "candidate_schema": "learning-resource-candidate/v1",
        "flow_schema": "learning-resource-flow/v1",
        "query": build_query(intent),
        "filters": intent_filters(intent),
        "intent": intent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_first": True,
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
    selection["used_web_fallback"] = used_web
    selection["needs_web_search"] = needs_web_search
    selection["source_runs"] = source_runs
    selection["work_files"] = work_files
    write_json(selection_json, selection)
    if not args.output:
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
