#!/usr/bin/env python3
"""Run offline smoke tests for the learning resource skill chain."""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_docx(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", xml)


def write_pptx(path: Path, slide_texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        for index, text in enumerate(slide_texts, 1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>",
            )


def write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    png_2x1 = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    path.write_bytes(base64.b64decode(png_2x1))


def start_static_server(directory: Path) -> tuple[http.server.ThreadingHTTPServer, threading.Thread, str]:
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


class SmokeRunner:
    def __init__(self, root: Path, work_dir: Path, keep_work: bool) -> None:
        self.root = root
        self.work_dir = work_dir
        self.keep_work = keep_work
        self.skills = root / "skills"
        self.results: list[tuple[str, str]] = []

    def script(self, *parts: str) -> str:
        return str(self.skills.joinpath(*parts))

    def command(self, name: str, cmd: list[str], expect_success: bool = True) -> subprocess.CompletedProcess[str]:
        result = run_cmd(cmd, self.root)
        ok = result.returncode == 0 if expect_success else result.returncode != 0
        self.results.append((name, "ok" if ok else "failed"))
        if not ok:
            print(f"\n[失败] {name}", file=sys.stderr)
            print("命令:", " ".join(cmd), file=sys.stderr)
            print("stdout:\n" + result.stdout, file=sys.stderr)
            print("stderr:\n" + result.stderr, file=sys.stderr)
            raise SystemExit(result.returncode or 1)
        return result

    def prepare(self) -> None:
        if self.work_dir.exists() and not self.keep_work:
            shutil.rmtree(self.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def test_web_to_selection(self) -> Path:
        search_results = self.work_dir / "search-results.json"
        task = self.work_dir / "task.json"
        candidates = self.work_dir / "web-candidates.json"
        analyzed = self.work_dir / "web-analyzed.json"
        ranking = self.work_dir / "web-ranking.json"
        selection = self.work_dir / "web-selection.json"

        write_json(
            search_results,
            {
                "query": "8岁 四则混合运算 练习题 可打印 PDF",
                "search_results": [
                    {
                        "title": "8岁四则混合运算可打印练习题 PDF",
                        "url": "https://example.edu.cn/math.pdf",
                        "snippet": "适合小学低年级儿童的数学练习，可直接打印。",
                    },
                    {
                        "title": "成人贷款下载器",
                        "url": "https://example.com/downloader.exe",
                        "snippet": "高速下载器 破解 成人 贷款",
                    },
                ],
            },
        )
        write_json(
            task,
            {
                "task_id": "task_001",
                "target_skill": "web-learning-search",
                "query": "8岁 四则混合运算 练习题 可打印 PDF",
                "filters": {
                    "learner_age": 8,
                    "subject": "数学",
                    "core_topic": "四则混合运算",
                    "resource_types": ["习题"],
                    "format_preferences": ["PDF"],
                },
            },
        )

        self.command(
            "web-learning-search",
            [
                sys.executable,
                self.script("web-learning-search", "scripts", "search_web_resources.py"),
                "--search-results-json",
                str(search_results),
                "--task-json",
                str(task),
                "-o",
                str(candidates),
            ],
        )
        self.command(
            "learning-resource-analyzer",
            [
                sys.executable,
                self.script("learning-resource-analyzer", "scripts", "analyze_candidates.py"),
                str(candidates),
                "-o",
                str(analyzed),
            ],
        )
        self.command(
            "learning-resource-ranker",
            [
                sys.executable,
                self.script("learning-resource-ranker", "scripts", "rank_candidates.py"),
                str(analyzed),
                "-o",
                str(ranking),
            ],
        )
        self.command(
            "learning-resource-selector",
            [
                sys.executable,
                self.script("learning-resource-selector", "scripts", "select_candidates.py"),
                str(ranking),
                "-o",
                str(selection),
            ],
        )

        selection_data = load_json(selection)
        assert_true(selection_data.get("status") == "awaiting_user_selection", "selector 应输出待用户选择状态")
        assert_true(selection_data.get("shown_count", 0) >= 1, "selector 应至少展示一个候选")
        return selection

    def test_source_first_flow(self) -> None:
        intent_json = self.work_dir / "source-first-intent.json"
        search_results = self.work_dir / "source-first-web-results.json"
        selection_json = self.work_dir / "source-first-selection.json"
        sample_smartedu_search = self.skills / "smartedu-resources" / "references" / "sample-search-response.json"
        sample_html = self.skills / "web-resource-profiler" / "references" / "sample-resource-page.html"

        write_json(
            intent_json,
            {
                "intent_schema": "learning-resource-intent/v1",
                "status": "ready",
                "intent_type": "topic_resource",
                "normalized_query": "8岁 四则混合运算 可打印练习题",
                "learner_age": 8,
                "learning_domain": "数学",
                "subject": "数学",
                "core_topic": "四则混合运算",
                "resource_goal": "练习",
                "resource_types": ["习题"],
                "format_preferences": ["pdf"],
                "execution_tasks": [
                    {
                        "task_id": "task_001",
                        "task_type": "source_search",
                        "target_skill": "source-first",
                        "action": "search",
                        "query": "8岁 四则混合运算 可打印练习题",
                        "filters": {
                            "learner_age": 8,
                            "learning_domain": "数学",
                            "subject": "数学",
                            "core_topic": "四则混合运算",
                            "resource_types": ["习题"],
                            "format_preferences": ["pdf"],
                        },
                        "download_policy": "after_user_selection",
                    }
                ],
            },
        )
        write_json(
            search_results,
            {
                "query": "8岁 四则混合运算 可打印练习题",
                "search_results": [
                    {
                        "title": "8岁四则混合运算可打印练习题 PDF",
                        "url": "https://example.edu.cn/math.pdf",
                        "snippet": "适合小学低年级儿童的数学练习，可直接打印。",
                    },
                    {
                        "title": "四则混合运算练习题讲义",
                        "url": "https://example.edu.cn/math-practice.docx",
                        "snippet": "包含加减乘除混合运算练习。",
                    },
                ],
            },
        )
        self.command(
            "learning-resource-flow-source-first",
            [
                sys.executable,
                self.script("learning-resource-flow", "scripts", "run_resource_flow.py"),
                "--intent-json",
                str(intent_json),
                "--smartedu-search-response-json",
                str(sample_smartedu_search),
                "--web-search-results-json",
                str(search_results),
                "--web-profile-html-file",
                str(sample_html),
                "--min-source-candidates",
                "3",
                "--work-dir",
                str(self.work_dir / "source-first-flow"),
                "-o",
                str(selection_json),
            ],
        )
        selection = load_json(selection_json)
        assert_true(selection.get("flow_schema") == "learning-resource-flow/v1", "source-first flow 应输出流程标记")
        assert_true(selection.get("source_first") is True, "source-first flow 应标记先查已优化来源")
        assert_true(selection.get("used_web_fallback") is True, "已优化来源候选不足时应启用 web fallback")
        sources = [item.get("source") for item in selection.get("source_runs") or []]
        assert_true("smartedu-resources:site-index" in sources, "source-first flow 应先加载 SmartEdu site-index 作为来源能力索引")
        assert_true("smartedu-resources" in sources, "source-first flow 应先调用 SmartEdu source")
        assert_true("web-learning-search" in sources, "source-first flow 候选不足时应调用 web-learning-search")
        assert_true("resource-source-discovery" in sources, "source-first flow 应接入来源发现")
        assert_true("web-resource-profiler" in sources, "source-first flow 应接入资源站画像")
        assert_true("generic-web-source" in sources, "source-first flow 应接入通用资源站抽取")
        assert_true(bool(selection.get("work_files", {}).get("smartedu_site_index")), "source-first flow 应记录 SmartEdu site-index 工作文件")
        assert_true(bool(selection.get("work_files", {}).get("source_discovery")), "source-first flow 应记录来源发现工作文件")
        assert_true(bool(selection.get("work_files", {}).get("generic_candidates")), "source-first flow 应记录通用抽取候选文件")
        assert_true(selection.get("shown_count", 0) >= 1, "source-first flow 应生成用户可选候选")

    def test_resource_flow_local_first(self) -> None:
        intent_json = self.work_dir / "local-first-intent.json"
        index_dir = self.work_dir / "local-first-index"
        library_dir = self.work_dir / "local-first-library"
        local_pdf = library_dir / "小学低年级" / "二年级" / "数学" / "四则混合运算" / "本地资料库" / "四则混合运算练习题_abcd1234.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n%%EOF\n")
        index_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            index_dir / "resources.json",
            {
                "index_schema": "learning-library-index/v1",
                "resources": [
                    {
                        "resource_key": "local-flow-001",
                        "title": "四则混合运算练习题",
                        "library_file": str(local_pdf),
                        "format": "pdf",
                        "resource_type": "习题",
                        "classification": {
                            "stage_or_age": "小学低年级",
                            "grade_or_phase": "二年级",
                            "domain_or_subject": "数学",
                            "topic_or_type": "四则混合运算",
                            "source_or_version": "本地资料库",
                        },
                        "classification_confidence": 0.9,
                        "needs_review": False,
                        "source_url": "local://四则混合运算练习题",
                        "sha256": "localflowsha001",
                    }
                ],
            },
        )
        write_json(
            intent_json,
            {
                "intent_schema": "learning-resource-intent/v1",
                "status": "ready",
                "intent_type": "topic_resource",
                "normalized_query": "8岁 四则混合运算 练习题",
                "learner_age": 8,
                "stage": "小学低年级",
                "grade": "二年级",
                "learning_domain": "数学",
                "subject": "数学",
                "core_topic": "四则混合运算",
                "resource_goal": "练习",
                "resource_types": ["习题"],
                "format_preferences": ["pdf"],
                "constraints": ["适合打印"],
                "ranking_profile": {"prefer": ["pdf", "可打印"], "avoid": ["强制下载器"]},
                "execution_tasks": [{"task_id": "task_001", "query": "8岁 四则混合运算 练习题", "filters": {"subject": "数学"}}],
            },
        )
        selection_json = self.work_dir / "local-first-selection.json"
        self.command(
            "learning-resource-flow-local-first",
            [
                sys.executable,
                self.script("learning-resource-flow", "scripts", "run_resource_flow.py"),
                "--intent-json",
                str(intent_json),
                "--local-index-file",
                str(index_dir / "resources.json"),
                "--local-satisfy-candidates",
                "1",
                "--min-source-candidates",
                "1",
                "--work-dir",
                str(self.work_dir / "local-first-flow"),
                "-o",
                str(selection_json),
            ],
        )
        selection = load_json(selection_json)
        assert_true(selection.get("used_local_candidates") is True, "flow 应优先使用本地资料库候选")
        sources = [item.get("source") for item in selection.get("source_runs") or []]
        assert_true("local-library-search" in sources, "flow 应调用 local-library-search")
        assert_true("smartedu-resources" not in sources, "本地候选足够时默认不应继续外部 source")
        assert_true(selection.get("options", [{}])[0].get("source_name") == "本地学习资料库", "本地候选应进入 selector")

    def test_resource_flow_download_archive(self) -> None:
        server_dir = self.work_dir / "flow-http"
        server_dir.mkdir(parents=True, exist_ok=True)
        resource_file = server_dir / "math-practice.pdf"
        resource_file.write_bytes(
            "%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n2 0 obj\n(四则混合运算 练习 可打印)\nendobj\n%%EOF\n".encode("utf-8")
        )
        server, thread, base_url = start_static_server(server_dir)
        try:
            intent_json = self.work_dir / "flow-download-intent.json"
            search_results = self.work_dir / "flow-download-web-results.json"
            smartedu_empty_search = self.work_dir / "flow-download-smartedu-empty.json"
            output_json = self.work_dir / "flow-download-selection.json"
            library_dir = self.work_dir / "flow-library"
            index_dir = self.work_dir / "flow-index"
            write_json(
                intent_json,
                {
                    "intent_schema": "learning-resource-intent/v1",
                    "status": "ready",
                    "intent_type": "topic_resource",
                    "normalized_query": "8岁 四则混合运算 可打印练习题",
                    "learner_age": 8,
                    "learning_domain": "数学",
                    "subject": "数学",
                    "core_topic": "四则混合运算",
                    "resource_goal": "练习",
                    "resource_types": ["习题"],
                    "format_preferences": ["pdf"],
                    "constraints": ["适合打印"],
                    "ranking_profile": {"prefer": ["pdf", "可打印"], "avoid": ["强制下载器", "成人化内容"]},
                    "execution_tasks": [{"task_id": "task_001", "query": "8岁 四则混合运算 可打印练习题"}],
                },
            )
            write_json(
                search_results,
                {
                    "query": "8岁 四则混合运算 可打印练习题",
                    "search_results": [
                        {
                            "title": "8岁四则混合运算可打印练习题 PDF",
                            "url": f"{base_url}/math-practice.pdf",
                            "snippet": "适合小学低年级儿童的数学练习，可直接打印。",
                        }
                    ],
                },
            )
            write_json(smartedu_empty_search, {"total": 0, "items": []})
            self.command(
                "learning-resource-flow-download-archive",
                [
                    sys.executable,
                    self.script("learning-resource-flow", "scripts", "run_resource_flow.py"),
                    "--intent-json",
                    str(intent_json),
                    "--skip-local-search",
                    "--web-search-results-json",
                    str(search_results),
                    "--smartedu-search-response-json",
                    str(smartedu_empty_search),
                    "--min-source-candidates",
                    "3",
                    "--work-dir",
                    str(self.work_dir / "flow-download-work"),
                    "--select",
                    "A",
                    "--library-dir",
                    str(library_dir),
                    "--index-dir",
                    str(index_dir),
                    "-o",
                    str(output_json),
                ],
            )
            result = load_json(output_json)
            assert_true(result.get("status") == "post_selection_completed", "flow 选择后应完成下载、归档和索引")
            post = result.get("post_selection") or {}
            assert_true((post.get("download") or {}).get("summary", {}).get("downloaded") == 1, "flow 应下载 1 个文件")
            assert_true((post.get("organize") or {}).get("summary", {}).get("organized") == 1, "flow 应归档 1 个文件")
            assert_true((index_dir / "resources.json").exists(), "flow 应更新外部索引 resources.json")
            assert_true(bool(list(library_dir.rglob("*.pdf"))), "最终资料库应包含真实 PDF 文件")
            assert_true(not list(library_dir.rglob("*.json")), "最终资料库不应包含 JSON 元数据")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_source_discovery_and_profiler(self) -> None:
        sample_candidates = self.skills / "resource-source-discovery" / "references" / "sample-web-candidates.json"
        source_discovery = self.work_dir / "source-discovery.json"
        site_profile = self.work_dir / "site-profile.json"
        generic_candidates = self.work_dir / "generic-candidates.json"
        sample_html = self.skills / "web-resource-profiler" / "references" / "sample-resource-page.html"

        self.command(
            "resource-source-discovery",
            [
                sys.executable,
                self.script("resource-source-discovery", "scripts", "discover_sources.py"),
                str(sample_candidates),
                "-o",
                str(source_discovery),
            ],
        )
        discovery_data = load_json(source_discovery)
        assert_true(discovery_data["summary"]["sources"] >= 1, "source discovery 应识别至少一个可用来源")
        assert_true(discovery_data["summary"]["rejected"] >= 1, "source discovery 应拒绝风险来源")

        self.command(
            "web-resource-profiler",
            [
                sys.executable,
                self.script("web-resource-profiler", "scripts", "profile_site.py"),
                "--url",
                "https://example.edu.cn/resources",
                "--html-file",
                str(sample_html),
                "-o",
                str(site_profile),
            ],
        )
        profile_data = load_json(site_profile)
        assert_true(profile_data["summary"]["profiled"] == 1, "profiler 应生成 1 个站点画像")
        profile = profile_data["profiles"][0]
        assert_true(profile["crawl_strategy"] == "generic_extract", "样例资源页应建议通用抽取")
        assert_true(len(profile.get("resource_links") or []) >= 2, "样例资源页应识别资源链接")

        self.command(
            "generic-web-source",
            [
                sys.executable,
                self.script("generic-web-source", "scripts", "extract_candidates.py"),
                "--site-profile-json",
                str(site_profile),
                "-o",
                str(generic_candidates),
            ],
        )
        generic_data = load_json(generic_candidates)
        generic_items = generic_data.get("candidates") or []
        assert_true(len(generic_items) >= 2, "generic-web-source 应抽取至少 2 个候选")
        assert_true(any(item.get("format") == "pdf" for item in generic_items), "generic-web-source 应包含 PDF 候选")
        assert_true(bool(generic_items[0].get("raw", {}).get("origin_page_url")), "通用抽取候选应保留原始页面 URL")

    def test_smartedu_resources(self) -> None:
        site_profile_json = self.work_dir / "smartedu-site-profile.json"
        catalogs_json = self.work_dir / "smartedu-catalogs.json"
        route_map_json = self.work_dir / "smartedu-route-map.json"
        site_index_json = self.work_dir / "smartedu-site-index.json"
        site_index_with_scan_json = self.work_dir / "smartedu-site-index-with-scan.json"
        page_profile_json = self.work_dir / "smartedu-page-profile.json"
        catalog_scan_json = self.work_dir / "smartedu-catalog-scan.json"
        site_scan_json = self.work_dir / "smartedu-site-scan.json"
        site_scan_detail_json = self.work_dir / "smartedu-site-scan-detail.json"
        site_index_detail_json = self.work_dir / "smartedu-site-index-detail.json"
        textbook_candidates_json = self.work_dir / "smartedu-textbook-candidates.json"
        textbook_work_dir = self.work_dir / "smartedu-textbook-work"
        search_candidates_json = self.work_dir / "smartedu-search-candidates.json"
        search_detail_candidates_json = self.work_dir / "smartedu-search-detail-candidates.json"
        explicit_detail_search_json = self.work_dir / "smartedu-explicit-detail-search.json"
        explicit_detail_output_json = self.work_dir / "smartedu-explicit-detail-output.json"
        explicit_detail_server_dir = self.work_dir / "smartedu-explicit-detail-http"
        detail_probe_json = self.work_dir / "smartedu-detail-probe.json"
        search_detail_dir = self.work_dir / "smartedu-search-details"
        candidates_json = self.work_dir / "smartedu-resource-candidates.json"
        sample_library = self.skills / "smartedu-resources" / "references" / "sample-librarylist.json"
        sample_page = self.skills / "smartedu-resources" / "references" / "sample-page.html"
        sample_textbooks = self.skills / "smartedu-resources" / "references" / "sample-textbooks.json"
        sample_search = self.skills / "smartedu-resources" / "references" / "sample-search-response.json"
        sample_detail = self.skills / "smartedu-resources" / "references" / "sample-detail.json"

        self.command(
            "smartedu-resources-site-profile",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "site-profile",
                "--library-list-json",
                str(sample_library),
                "--header",
                "X-Test-Auth: test-marker-value",
                "-o",
                str(site_profile_json),
            ],
        )
        site_profile = load_json(site_profile_json)
        assert_true(site_profile.get("source_profile_schema") == "learning-resource-source-profile/v1", "SmartEdu 应输出站点能力画像")
        assert_true(site_profile.get("routing_policy", {}).get("type_binding") is False, "SmartEdu 来源不应与资源类型硬绑定")
        assert_true(site_profile.get("access_policy", {}).get("auth_context") is True, "SmartEdu 能力画像应标记授权上下文")
        assert_true(site_profile.get("catalog_summary", {}).get("textbook_catalogs") == 1, "能力画像应识别教材是站内分支")
        assert_true("test-marker-value" not in site_profile_json.read_text(encoding="utf-8"), "能力画像不应泄露授权 header 原文")

        self.command(
            "smartedu-resources-route-map",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "route-map",
                "--library-list-json",
                str(sample_library),
                "-o",
                str(route_map_json),
            ],
        )
        route_map = load_json(route_map_json)
        routes = route_map.get("routes") or []
        assert_true(route_map.get("route_map_schema") == "smartedu-route-map/v1", "SmartEdu 应输出栏目路由图")
        assert_true("duplicates_removed" in route_map.get("summary", {}), "路由图应报告去重数量")
        assert_true(any(item.get("scan_strategy") == "internal_adapter" for item in routes), "路由图应包含教材内部适配分支")
        assert_true(any(item.get("scan_strategy") == "search_then_detail" for item in routes), "路由图应包含搜索到详情分支")
        assert_true(any(item.get("detail_url_templates") for item in routes), "路由图应包含详情 URL 模板")

        self.command(
            "smartedu-resources-site-index",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "site-index",
                "--route-map-json",
                str(route_map_json),
                "-o",
                str(site_index_json),
            ],
        )
        site_index = load_json(site_index_json)
        assert_true(site_index.get("site_index_schema") == "smartedu-site-index/v1", "SmartEdu 应输出全站索引")
        assert_true(site_index.get("summary", {}).get("routes") == len(routes), "全站索引默认应覆盖全部 route")
        assert_true(len(site_index.get("scan_plan") or []) == len(routes), "全站索引应为每条 route 输出扫描计划")
        assert_true(site_index.get("coverage", {}).get("scan_strategies", {}).get("search_then_detail", 0) >= 1, "全站索引应统计搜索到详情 route")
        assert_true(site_index.get("coverage", {}).get("scan_strategies", {}).get("internal_adapter", 0) >= 1, "全站索引应统计内部适配 route")

        self.command(
            "smartedu-resources-page-profile",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "page-profile",
                "--url",
                "https://basic.smartedu.cn/",
                "--html-file",
                str(sample_page),
                "-o",
                str(page_profile_json),
            ],
        )
        page_profile = load_json(page_profile_json)
        assert_true(page_profile.get("page_profile_schema") == "smartedu-page-profile/v1", "SmartEdu 应输出页面画像")
        assert_true(page_profile.get("summary", {}).get("api_hints", 0) >= 3, "页面画像应识别接口线索")
        assert_true(page_profile.get("summary", {}).get("detail_hints", 0) >= 1, "页面画像应识别详情线索")
        assert_true(page_profile.get("summary", {}).get("resource_link_hints", 0) >= 1, "页面画像应识别资源链接线索")
        assert_true("script_sources" in page_profile.get("summary", {}), "页面画像应报告脚本来源数量")
        assert_true("search-resources" in page_profile.get("recommended_next_actions", []), "页面画像应建议搜索资源动作")

        self.command(
            "smartedu-resources-scan-catalog",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "scan-catalog",
                "--route-map-json",
                str(route_map_json),
                "--type",
                "qualityCourse",
                "--query",
                "三年级数学",
                "--search-response-json",
                str(sample_search),
                "-o",
                str(catalog_scan_json),
            ],
        )
        catalog_scan = load_json(catalog_scan_json)
        scan_candidates = catalog_scan.get("candidates") or []
        assert_true(catalog_scan.get("scan_schema") == "smartedu-catalog-scan/v1", "SmartEdu 应输出栏目扫描结果")
        assert_true(catalog_scan.get("summary", {}).get("routes_scanned") == 1, "栏目扫描应扫描 1 条 route")
        assert_true(len(scan_candidates) == 2, "栏目扫描应归一化搜索候选")
        assert_true(all(item.get("raw", {}).get("smartedu_route_id") for item in scan_candidates), "栏目扫描候选应保留 route 追踪信息")

        self.command(
            "smartedu-resources-scan-site",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "scan-site",
                "--route-map-json",
                str(route_map_json),
                "--catalog",
                "syncClassroom",
                "--query",
                "三年级数学",
                "--route-limit",
                "2",
                "--search-response-json",
                str(sample_search),
                "-o",
                str(site_scan_json),
            ],
        )
        site_scan = load_json(site_scan_json)
        site_candidates = site_scan.get("candidates") or []
        assert_true(site_scan.get("site_scan_schema") == "smartedu-site-scan/v1", "SmartEdu 应输出站点扫描结果")
        assert_true(site_scan.get("summary", {}).get("routes_scanned") == 2, "站点扫描应批量扫描 2 条 route")
        assert_true(site_scan.get("summary", {}).get("raw_candidates") >= 2, "站点扫描应汇总原始候选")
        assert_true(site_scan.get("summary", {}).get("duplicates_removed") >= 1, "站点扫描应去重重复候选")
        assert_true(len(site_candidates) == 2, "站点扫描去重后应保留标准候选")

        self.command(
            "smartedu-resources-site-index-with-scan",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "site-index",
                "--route-map-json",
                str(route_map_json),
                "--site-scan-json",
                str(site_scan_json),
                "-o",
                str(site_index_with_scan_json),
            ],
        )
        site_index_with_scan = load_json(site_index_with_scan_json)
        assert_true(site_index_with_scan.get("summary", {}).get("candidates") == len(site_candidates), "全站索引应合并 scan-site 候选")
        assert_true(site_index_with_scan.get("summary", {}).get("route_scan_summary", {}).get("routes_scanned") == 2, "全站索引应合并扫描摘要")

        self.command(
            "smartedu-resources-catalogs",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "list-catalogs",
                "--library-list-json",
                str(sample_library),
                "-o",
                str(catalogs_json),
            ],
        )
        catalogs = load_json(catalogs_json)
        assert_true(catalogs["summary"]["resource_catalogs"] >= 1, "SmartEdu 栏目画像应包含通用资源栏目")
        assert_true(catalogs["summary"]["textbook_catalogs"] == 1, "SmartEdu 栏目画像应识别站内教材资源分支")
        assert_true(all(item.get("known_skill") == "smartedu-resources" for item in catalogs.get("catalogs") or []), "SmartEdu 所有站内栏目应统一路由到 smartedu-resources")

        shutil.copytree(sample_textbooks.parent, textbook_work_dir / "refs", dirs_exist_ok=True)
        (textbook_work_dir / "data").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sample_textbooks, textbook_work_dir / "data" / "textbooks.json")
        self.command(
            "smartedu-resources-textbooks",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "textbook-candidates",
                "--stage",
                "小学",
                "--grade",
                "三年级",
                "--subject",
                "数学",
                "--work-dir",
                str(textbook_work_dir),
                "-o",
                str(textbook_candidates_json),
            ],
        )
        textbook_data = load_json(textbook_candidates_json)
        textbook_candidates = textbook_data.get("candidates") or []
        assert_true(textbook_data.get("source_skill") == "smartedu-resources", "教材候选应由 smartedu-resources 对外输出")
        assert_true(textbook_data.get("internal_adapter") == "tchMaterial", "教材候选应标记内部教材分支")
        assert_true(len(textbook_candidates) == 1, "SmartEdu 教材候选应按条件过滤")
        assert_true(textbook_candidates[0].get("source") == "smartedu-resources", "教材候选 source 应统一为 smartedu-resources")
        assert_true(textbook_candidates[0].get("raw", {}).get("internal_adapter") == "tchMaterial", "教材候选应保留内部适配器标记")

        self.command(
            "smartedu-resources-search",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "search-resources",
                "--query",
                "三年级数学",
                "--search-response-json",
                str(sample_search),
                "--header",
                "X-Test-Auth: test-marker-value",
                "-o",
                str(search_candidates_json),
            ],
        )
        search_data = load_json(search_candidates_json)
        search_candidates = search_data.get("candidates") or []
        assert_true(len(search_candidates) == 2, "SmartEdu 搜索响应应归一化为候选")
        assert_true(search_data.get("summary", {}).get("auth_context") is True, "SmartEdu 授权上下文应被标记但不泄露")
        assert_true("test-marker-value" not in search_candidates_json.read_text(encoding="utf-8"), "SmartEdu 输出不应包含授权 header 原文")
        assert_true(all(item.get("source") == "smartedu-resources" for item in search_candidates), "搜索候选 source 应正确")
        assert_true(any(item.get("raw", {}).get("smartedu_search_item") for item in search_candidates), "搜索候选应保留原始搜索项")
        assert_true(all(item.get("downloadable") is False for item in search_candidates), "搜索候选未解析详情前不应标记可下载")

        detail_fixture = load_json(sample_detail)
        detail_fixture["id"] = "qc-math-001"
        search_detail_dir.mkdir(parents=True, exist_ok=True)
        write_json(search_detail_dir / "qc-math-001.json", detail_fixture)
        self.command(
            "smartedu-resources-search-details",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "search-resources",
                "--query",
                "三年级数学",
                "--search-response-json",
                str(sample_search),
                "--fetch-details",
                "--detail-dir",
                str(search_detail_dir),
                "--offline-details-only",
                "-o",
                str(search_detail_candidates_json),
            ],
        )
        search_detail_data = load_json(search_detail_candidates_json)
        detail_candidates = search_detail_data.get("candidates") or []
        detail_formats = {item.get("format") for item in detail_candidates}
        assert_true({"m3u8", "pdf", "jpg"}.issubset(detail_formats), "搜索详情追踪应展开 ti_items 文件项")
        assert_true(search_detail_data.get("summary", {}).get("details_fetched") == 1, "搜索详情追踪应命中 1 个详情")
        assert_true(search_detail_data.get("summary", {}).get("detail_failures") == 1, "缺失详情应记录失败并保留搜索候选")
        assert_true(any(item.get("downloadable") is True for item in detail_candidates), "详情文件项候选应可进入后续下载判断")
        detail_summaries = [
            item.get("raw", {}).get("smartedu_detail")
            for item in detail_candidates
            if isinstance(item.get("raw", {}).get("smartedu_detail"), dict)
        ]
        assert_true(any(item.get("detail_status") == "ok_with_file_items" for item in detail_summaries), "详情候选应回写可展开状态")
        assert_true(any(item.get("detail_status") == "detail_not_found_in_dir" for item in detail_summaries), "详情失败候选应回写失败分类")

        explicit_detail_server_dir.mkdir(parents=True, exist_ok=True)
        explicit_detail_fixture = load_json(sample_detail)
        explicit_detail_fixture["id"] = "explicit-math-001"
        write_json(explicit_detail_server_dir / "explicit-detail.json", explicit_detail_fixture)
        explicit_server, explicit_thread, explicit_base_url = start_static_server(explicit_detail_server_dir)
        try:
            write_json(
                explicit_detail_search_json,
                {
                    "data": {
                        "items": [
                            {
                                "title": "显式详情 URL 数学资源",
                                "detailUrl": "https://basic.smartedu.cn/resourceCenter/detail?contentType=NDR_Explicit&contentId=explicit-math-001&catalogType=resourceCenter&subCatalog=paper",
                                "detailJsonUrl": f"{explicit_base_url}/explicit-detail.json",
                                "resourceTypeName": "文档",
                                "subjectName": "数学",
                            }
                        ]
                    }
                },
            )
            self.command(
                "smartedu-resources-explicit-detail-url",
                [
                    sys.executable,
                    self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                    "search-resources",
                    "--query",
                    "显式详情 URL 数学资源",
                    "--search-response-json",
                    str(explicit_detail_search_json),
                    "--fetch-details",
                    "-o",
                    str(explicit_detail_output_json),
                ],
            )
        finally:
            explicit_server.shutdown()
            explicit_server.server_close()
            explicit_thread.join(timeout=5)
        explicit_detail_data = load_json(explicit_detail_output_json)
        explicit_candidates = explicit_detail_data.get("candidates") or []
        explicit_summaries = [
            item.get("raw", {}).get("smartedu_detail")
            for item in explicit_candidates
            if isinstance(item.get("raw", {}).get("smartedu_detail"), dict)
        ]
        assert_true(explicit_detail_data.get("summary", {}).get("details_fetched") == 1, "显式详情 JSON URL 应可直接展开")
        assert_true(any(item.get("detail_endpoint_family") == "search-item-detail-json" for item in explicit_summaries), "详情摘要应记录显式详情 URL 模板族")
        assert_true(any(item.get("downloadable") is True for item in explicit_candidates), "显式详情 JSON 应展开为可下载候选")

        self.command(
            "smartedu-resources-detail-probe",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "detail-probe",
                "--query",
                "三年级数学",
                "--search-response-json",
                str(sample_search),
                "--detail-dir",
                str(search_detail_dir),
                "--offline-details-only",
                "-o",
                str(detail_probe_json),
            ],
        )
        detail_probe = load_json(detail_probe_json)
        probes = detail_probe.get("probes") or []
        detail_matrix = detail_probe.get("detail_matrix") or []
        assert_true(detail_probe.get("detail_probe_schema") == "smartedu-detail-probe/v1", "SmartEdu 应输出详情探测结果")
        assert_true(len(probes) == 2, "详情探测应覆盖搜索候选")
        assert_true(detail_probe.get("summary", {}).get("matrix_rows") == 2, "详情探测应按候选字段输出矩阵")
        assert_true(detail_probe.get("summary", {}).get("status_counts", {}).get("ok_with_file_items") == 1, "详情探测应识别可展开详情")
        assert_true(detail_probe.get("summary", {}).get("status_counts", {}).get("detail_not_found_in_dir") == 1, "详情探测应识别缺失详情")
        assert_true(any(row.get("tab_code") == "qualityCourse" and row.get("conclusion") == "公开可取" for row in detail_matrix), "详情矩阵应识别公开可取栏目")
        assert_true(any(row.get("tab_code") == "basicWork" and row.get("conclusion") == "模板未知" for row in detail_matrix), "详情矩阵应识别模板未知栏目")
        assert_true(probes[0].get("detail_access_policy") == "public_detail", "命中详情的候选应标记公开详情可取")
        assert_true(probes[0].get("file_item_count", 0) >= 3, "详情探测应统计 ti_items 数量")

        self.command(
            "smartedu-resources-scan-site-details",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "scan-site",
                "--route-map-json",
                str(route_map_json),
                "--type",
                "qualityCourse",
                "--query",
                "三年级数学",
                "--route-limit",
                "1",
                "--search-response-json",
                str(sample_search),
                "--fetch-details",
                "--detail-dir",
                str(search_detail_dir),
                "--offline-details-only",
                "-o",
                str(site_scan_detail_json),
            ],
        )
        self.command(
            "smartedu-resources-site-index-detail-coverage",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "site-index",
                "--route-map-json",
                str(route_map_json),
                "--site-scan-json",
                str(site_scan_detail_json),
                "-o",
                str(site_index_detail_json),
            ],
        )
        site_index_detail = load_json(site_index_detail_json)
        assert_true(site_index_detail.get("summary", {}).get("detail_coverage_routes") == 1, "全站索引应聚合 route 级详情覆盖")
        assert_true(site_index_detail.get("detail_coverage", [{}])[0].get("detail_status_counts", {}).get("ok_with_file_items") >= 1, "全站索引应统计详情成功状态")
        assert_true(site_index_detail.get("summary", {}).get("route_scan_summary", {}).get("detail_access_policy_counts", {}).get("public_detail") >= 1, "全站索引应统计详情访问策略")

        self.command(
            "smartedu-resources-candidates",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_resources.py"),
                "candidates-from-detail",
                "--catalog",
                "qualityCourse",
                "--sub-catalog",
                "course",
                "--detail-json",
                str(sample_detail),
                "-o",
                str(candidates_json),
            ],
        )
        candidates = load_json(candidates_json).get("candidates") or []
        formats = {item.get("format") for item in candidates}
        assert_true({"m3u8", "pdf", "jpg"}.issubset(formats), "SmartEdu 详情应抽取视频、PDF、图片候选")
        assert_true(all(item.get("source") == "smartedu-resources" for item in candidates), "SmartEdu 候选 source 应正确")
        assert_true(any(item.get("requires_auth") for item in candidates), "私有 NDR 资源应标记需要授权")
        assert_true(bool(candidates[0].get("raw", {}).get("smartedu_item")), "候选应保留原始 ti_item")

    def test_smartedu_browser_session_offline(self) -> None:
        state_json = self.work_dir / "smartedu-browser" / "state.json"
        summary_json = self.work_dir / "smartedu-browser" / "session-summary.json"
        export_json = self.work_dir / "smartedu-browser-export.json"
        check_json = self.work_dir / "smartedu-browser-check.json"
        write_json(
            state_json,
            {
                "cookies": [
                    {
                        "name": "SESSION",
                        "value": "secret-cookie-value",
                        "domain": ".basic.smartedu.cn",
                        "path": "/",
                        "expires": 1812345678,
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "Lax",
                    }
                ],
                "origins": [
                    {
                        "origin": "https://basic.smartedu.cn",
                        "localStorage": [{"name": "token", "value": "secret-local-token"}],
                    }
                ],
            },
        )
        self.command(
            "smartedu-browser-export-context",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_browser_session.py"),
                "export-context",
                "--state-json",
                str(state_json),
                "--summary-json",
                str(summary_json),
                "-o",
                str(export_json),
            ],
        )
        exported = load_json(export_json)
        export_text = export_json.read_text(encoding="utf-8")
        assert_true(exported.get("browser_session_schema") == "smartedu-browser-session/v1", "浏览器会话应输出脱敏摘要")
        assert_true(exported.get("auth_context") is True, "浏览器 state 中有 cookie 时应标记授权上下文")
        assert_true("basic.smartedu.cn" in exported.get("smartedu_cookie_domains", []), "浏览器会话应记录 SmartEdu cookie 域")
        assert_true("secret-cookie-value" not in export_text and "secret-local-token" not in export_text, "浏览器会话摘要不得泄露 cookie 或 localStorage 原文")

        self.command(
            "smartedu-browser-check-offline",
            [
                sys.executable,
                self.script("smartedu-resources", "scripts", "smartedu_browser_session.py"),
                "check",
                "--offline",
                "--state-json",
                str(state_json),
                "-o",
                str(check_json),
            ],
        )
        checked = load_json(check_json)
        assert_true(checked.get("offline") is True, "离线 check 不应发起网络请求")
        assert_true(checked.get("probes") == [], "离线 check 不应产生网络探针")
        assert_true("secret-cookie-value" not in check_json.read_text(encoding="utf-8"), "离线 check 不应泄露 cookie 原文")

    def test_multiformat_analyzer(self) -> None:
        fixture_dir = self.work_dir / "analyzer-fixtures"
        docx_file = fixture_dir / "四则混合运算讲义.docx"
        pptx_file = fixture_dir / "分数认识课件.pptx"
        png_file = fixture_dir / "恐龙百科图卡.png"
        html_file = fixture_dir / "risk.html"
        fake_pdf_file = fixture_dir / "login.pdf"
        candidates_json = self.work_dir / "multiformat-candidates.json"
        analyzed_json = self.work_dir / "multiformat-analyzed.json"

        write_docx(docx_file, "四则混合运算 练习 可打印")
        write_pptx(pptx_file, ["分数初步认识 课件", "三年级数学练习"])
        write_png(png_file)
        html_file.write_text(
            "<!doctype html><html><head><title>风险下载页</title></head>"
            "<body>高速下载器 免费破解 成人 贷款</body></html>",
            encoding="utf-8",
        )
        fake_pdf_file.write_text("<html><body>请登录后查看资源 会员专享</body></html>", encoding="utf-8")
        write_json(
            candidates_json,
            {
                "candidate_schema": "learning-resource-candidate/v1",
                "candidates": [
                    {"title": "四则混合运算讲义", "format": "docx", "local_file": str(docx_file), "source_url": "file://docx"},
                    {"title": "分数认识课件", "format": "pptx", "local_file": str(pptx_file), "source_url": "file://pptx"},
                    {"title": "恐龙百科图卡", "format": "png", "local_file": str(png_file), "source_url": "file://png"},
                    {"title": "风险下载页", "format": "html", "local_file": str(html_file), "source_url": "file://html"},
                    {"title": "伪装 PDF 登录页", "format": "pdf", "local_file": str(fake_pdf_file), "source_url": "file://login"},
                ],
            },
        )

        self.command(
            "multiformat-analyzer",
            [
                sys.executable,
                self.script("learning-resource-analyzer", "scripts", "analyze_candidates.py"),
                str(candidates_json),
                "-o",
                str(analyzed_json),
            ],
        )
        analyzed = load_json(analyzed_json)
        by_title = {item["title"]: item for item in analyzed.get("candidates") or []}
        doc_analysis = by_title["四则混合运算讲义"]["raw"]["analysis"]
        ppt_analysis = by_title["分数认识课件"]["raw"]["analysis"]
        png_analysis = by_title["恐龙百科图卡"]["raw"]["analysis"]
        risk_analysis = by_title["风险下载页"]["raw"]["analysis"]
        fake_pdf_analysis = by_title["伪装 PDF 登录页"]["raw"]["analysis"]
        assert_true("四则混合运算" in doc_analysis.get("text_sample", ""), "DOCX 应提取正文样本")
        assert_true(ppt_analysis.get("signals", {}).get("slide_count") == 2, "PPTX 应提取幻灯片数量")
        assert_true(png_analysis.get("signals", {}).get("width") == 2, "PNG 应提取图片宽度")
        assert_true(any("成人" in item for item in risk_analysis.get("warnings") or []), "HTML 风险页应识别成人化风险词")
        assert_true(fake_pdf_analysis.get("detected_format") == "html", "声明为 PDF 的 HTML 应被识别为 HTML")
        assert_true(any("登录" in item or "权限" in item for item in fake_pdf_analysis.get("warnings") or []), "登录页伪装资源应被风险提示")

    def test_smartedu_downloader_auth_policy(self) -> None:
        selection_json = self.work_dir / "smartedu-selection.json"
        skipped_json = self.work_dir / "smartedu-download-skipped.json"
        probed_json = self.work_dir / "smartedu-download-probed.json"
        browser_probed_json = self.work_dir / "smartedu-download-browser-probed.json"
        attempted_json = self.work_dir / "smartedu-download-attempted.json"
        browser_state_json = self.work_dir / "smartedu-browser-downloader" / "state.json"
        write_json(
            browser_state_json,
            {
                "cookies": [
                    {
                        "name": "SESSION",
                        "value": "secret-browser-cookie",
                        "domain": ".basic.smartedu.cn",
                        "path": "/",
                    }
                ],
                "origins": [],
            },
        )
        write_json(
            selection_json,
            {
                "selection_schema": "learning-resource-selection/v1",
                "options": [
                    {
                        "option_id": "A",
                        "title": "SmartEdu 分数讲义",
                        "source_url": "http://127.0.0.1:9/private.pdf",
                        "format": "pdf",
                        "resource_type": "文档",
                        "requires_auth": True,
                        "candidate": {
                            "source": "smartedu-resources",
                            "title": "SmartEdu 分数讲义",
                            "source_url": "http://127.0.0.1:9/private.pdf",
                            "format": "pdf",
                            "resource_type": "文档",
                            "requires_auth": True,
                            "raw": {
                                "url_candidates": [
                                    "http://127.0.0.1:9/private.pdf",
                                    "http://127.0.0.1:9/public.pdf"
                                ]
                            },
                        },
                    }
                ],
            },
        )
        self.command(
            "smartedu-downloader-skips-auth",
            [
                sys.executable,
                self.script("learning-resource-downloader", "scripts", "download_selected.py"),
                str(selection_json),
                "--select",
                "A",
                "-o",
                str(skipped_json),
            ],
            expect_success=False,
        )
        skipped = load_json(skipped_json)
        assert_true(skipped.get("skipped", [{}])[0].get("reason") == "需要登录或授权访问", "默认应跳过授权资源")

        self.command(
            "smartedu-downloader-probe-auth",
            [
                sys.executable,
                self.script("learning-resource-downloader", "scripts", "download_selected.py"),
                str(selection_json),
                "--select",
                "A",
                "--allow-auth",
                "--probe-only",
                "--header",
                "X-Test-Auth: test-marker-value",
                "--timeout",
                "1",
                "-o",
                str(probed_json),
            ],
            expect_success=False,
        )
        probed = load_json(probed_json)
        assert_true(probed.get("probe_only") is True, "probe-only 模式应被标记")
        assert_true(len(probed.get("probed") or []) == 1, "probe-only 应输出探测结果")
        assert_true(len(probed["probed"][0].get("url_results") or []) == 2, "probe-only 应探测 url_candidates")
        assert_true(probed["probed"][0].get("accessible") is False, "不可达测试 URL 应标记不可访问")
        assert_true("test-marker-value" not in probed_json.read_text(encoding="utf-8"), "探测输出不应包含授权 header 原文")

        self.command(
            "smartedu-downloader-browser-probe-auth",
            [
                sys.executable,
                self.script("learning-resource-downloader", "scripts", "download_selected.py"),
                str(selection_json),
                "--select",
                "A",
                "--allow-auth",
                "--probe-only",
                "--browser-state",
                str(browser_state_json),
                "--timeout",
                "1",
                "-o",
                str(browser_probed_json),
            ],
            expect_success=False,
        )
        browser_probed = load_json(browser_probed_json)
        browser_probe_results = browser_probed["probed"][0].get("url_results") or []
        assert_true(browser_probed.get("auth_context") is True, "browser state 应作为授权上下文")
        assert_true(browser_probed.get("browser_state_context") is True, "下载探测应标记 browser state 上下文")
        assert_true(any(item.get("source") == "browser_state" for item in browser_probe_results), "probe-only 应尝试 browser state 探测")
        assert_true("secret-browser-cookie" not in browser_probed_json.read_text(encoding="utf-8"), "browser state 探测输出不应泄露 cookie 原文")

        self.command(
            "smartedu-downloader-auth-attempt",
            [
                sys.executable,
                self.script("learning-resource-downloader", "scripts", "download_selected.py"),
                str(selection_json),
                "--select",
                "A",
                "--allow-auth",
                "--header",
                "X-Test-Auth: test-marker-value",
                "--timeout",
                "1",
                "-o",
                str(attempted_json),
            ],
            expect_success=False,
        )
        attempted = load_json(attempted_json)
        assert_true(attempted.get("auth_context") is True, "显式授权下载应标记 auth_context")
        assert_true(len(attempted.get("failures") or []) == 1, "无可达测试 URL 时应记录失败")
        assert_true("public.pdf" in attempted["failures"][0].get("error", ""), "下载器应尝试 url_candidates")
        assert_true("test-marker-value" not in attempted_json.read_text(encoding="utf-8"), "下载输出不应包含授权 header 原文")

    def test_library_chain(self) -> None:
        downloads_dir = self.work_dir / "downloads"
        library_dir = self.work_dir / "学习资料库"
        index_dir = self.work_dir / "index"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        local_pdf = downloads_dir / "四则混合运算练习题.pdf"
        local_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n%%EOF\n")

        download_json = self.work_dir / "download-result.json"
        organize_json = self.work_dir / "organize-result.json"
        index_update_json = self.work_dir / "index-update.json"
        local_candidates = self.work_dir / "local-candidates.json"
        local_analyzed = self.work_dir / "local-analyzed.json"
        local_ranking = self.work_dir / "local-ranking.json"

        write_json(
            download_json,
            {
                "download_schema": "learning-resource-download/v1",
                "status": "completed",
                "downloaded_files": [
                    {
                        "option_id": "A",
                        "title": "四则混合运算练习题",
                        "source_url": "https://example.edu.cn/math.pdf",
                        "local_file": str(local_pdf),
                        "format": "pdf",
                        "resource_type": "习题",
                        "sha256": "smokehash001",
                        "candidate": {
                            "source": "smoke",
                            "source_name": "示例来源",
                            "title": "四则混合运算练习题",
                            "format": "pdf",
                            "subject": "数学",
                            "topic": "四则混合运算",
                            "resource_type": "习题",
                            "metadata_confidence": 0.82,
                        },
                    }
                ],
                "skipped": [],
                "failures": [],
                "work_dir": str(self.work_dir),
            },
        )

        self.command(
            "learning-library-organizer",
            [
                sys.executable,
                self.script("learning-library-organizer", "scripts", "organize_downloads.py"),
                str(download_json),
                "--library-dir",
                str(library_dir),
                "--work-dir",
                str(self.work_dir),
                "-o",
                str(organize_json),
            ],
        )
        organize_data = load_json(organize_json)
        assert_true(organize_data["summary"]["organized"] == 1, "organizer 应归档 1 个文件")
        assert_true(not list(library_dir.rglob("*.json")), "最终资料库不应包含 JSON 文件")

        self.command(
            "learning-library-index",
            [
                sys.executable,
                self.script("learning-library-index", "scripts", "update_index.py"),
                str(organize_json),
                "--index-dir",
                str(index_dir),
                "--library-dir",
                str(library_dir),
                "-o",
                str(index_update_json),
            ],
        )
        assert_true((index_dir / "resources.json").exists(), "index 应生成 resources.json")

        self.command(
            "learning-library-index-protects-library",
            [
                sys.executable,
                self.script("learning-library-index", "scripts", "update_index.py"),
                str(organize_json),
                "--index-dir",
                str(library_dir / "index"),
                "--library-dir",
                str(library_dir),
            ],
            expect_success=False,
        )

        self.command(
            "local-library-search",
            [
                sys.executable,
                self.script("local-library-search", "scripts", "search_local_library.py"),
                "--query",
                "四则混合运算 练习题",
                "--index-file",
                str(index_dir / "resources.json"),
                "-o",
                str(local_candidates),
            ],
        )
        local_data = load_json(local_candidates)
        assert_true(len(local_data.get("candidates") or []) == 1, "local search 应命中 1 个本地候选")
        assert_true(bool(local_data["candidates"][0].get("local_file")), "本地候选应包含 local_file")

        self.command(
            "local-candidate-analyzer",
            [
                sys.executable,
                self.script("learning-resource-analyzer", "scripts", "analyze_candidates.py"),
                str(local_candidates),
                "-o",
                str(local_analyzed),
            ],
        )
        self.command(
            "local-candidate-ranker",
            [
                sys.executable,
                self.script("learning-resource-ranker", "scripts", "rank_candidates.py"),
                str(local_analyzed),
                "-o",
                str(local_ranking),
            ],
        )
        ranking_data = load_json(local_ranking)
        assert_true(ranking_data.get("total") == 1, "本地候选应可进入 ranker")

    def run(self) -> None:
        self.prepare()
        self.test_web_to_selection()
        self.test_source_first_flow()
        self.test_resource_flow_local_first()
        self.test_resource_flow_download_archive()
        self.test_source_discovery_and_profiler()
        self.test_smartedu_resources()
        self.test_smartedu_browser_session_offline()
        self.test_multiformat_analyzer()
        self.test_smartedu_downloader_auth_policy()
        self.test_library_chain()
        print("Smoke tests passed")
        for name, status in self.results:
            print(f"- {name}: {status}")
        print(f"work_dir: {self.work_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline smoke tests for learning resource skills")
    parser.add_argument("--work-dir", default=".learning-resource-work/smoke", help="Temporary smoke test work directory")
    parser.add_argument("--keep-work", action="store_true", help="Keep existing work directory contents")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    SmokeRunner(root, Path(args.work_dir), args.keep_work).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
