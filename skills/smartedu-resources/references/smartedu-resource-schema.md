# SmartEdu 通用资源输出契约

## 站点能力画像

`site-profile` 输出 `learning-resource-source-profile/v1`，供总控流程在调用搜索前了解本来源能力。

```json
{
  "source_profile_schema": "learning-resource-source-profile/v1",
  "source_skill": "smartedu-resources",
  "source_name": "国家中小学智慧教育平台",
  "site_url": "https://basic.smartedu.cn/",
  "routing_policy": {
    "as_candidate_source": true,
    "type_binding": false,
    "topic_binding": false
  },
  "capabilities": [],
  "resource_coverage": {
    "resource_types": [],
    "formats": [],
    "default_search_tabs": []
  },
  "access_policy": {
    "supports_auth_context": true,
    "auth_context": false,
    "secret_redaction": "输出只记录 auth_context，不写入 token、cookie、authorization 或 header 原文。"
  },
  "catalog_summary": {},
  "catalog_sample": []
}
```

该画像只说明来源能力，不代表本来源一定应被选中；来源选择仍应进入统一搜索、发现、分析、评分和用户选择流程。

## 候选输出

`smartedu-resources` 输出 `learning-resource-candidate/v1`。

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "smartedu-resources",
  "query": "",
  "filters": {},
  "candidates": [],
  "summary": {
    "details": 0,
    "items_seen": 0,
    "candidates": 0,
    "skipped": 0
  }
}
```

候选中的 `raw.smartedu_item` 保留原始 `ti_items` 文件项。`source_url` 优先使用可识别的文件或播放地址；如果只有私有 NDR 地址，`requires_auth=true`。

站内搜索候选中的 `raw.smartedu_search_item` 保留搜索结果原始项。此类候选通常只有详情页或元数据，因此：

```json
{
  "downloadable": false,
  "raw": {
    "warnings": ["搜索结果候选尚未解析详情文件项"]
  }
}
```

后续应继续抓取详情 JSON，并用 `candidates-from-detail` 解析为可下载或可播放的文件项候选。

当使用 `search-resources --fetch-details` 时，输出仍为 `learning-resource-candidate/v1`，但候选会优先来自详情 `ti_items`：

```json
{
  "summary": {
    "fetch_details": true,
    "details_fetched": 1,
    "detail_items_seen": 3,
    "detail_failures": 0
  },
  "candidates": [
    {
      "downloadable": true,
      "raw": {
        "smartedu_item": {},
        "url_candidates": []
      }
    }
  ]
}
```

如果某个搜索项无法获取详情，应保留搜索候选并在 `detail_failures` 中记录失败原因。

## 授权上下文

联网命令可以从运行环境读取授权信息：

```text
SMARTEDU_ACCESS_TOKEN
SMARTEDU_COOKIE
SMARTEDU_AUTHORIZATION
SMARTEDU_HEADERS
SMARTEDU_SDP_APP_ID
```

也可以使用命令行参数：

```text
--access-token
--cookie
--header "Name: value"
```

输出中只允许出现：

```json
{
  "summary": {
    "auth_context": true
  }
}
```

不得把 token、cookie、authorization 或自定义 header 的原文写入候选、日志、资料库、索引或计划文档。

新版搜索端点 `https://x-search.ykt.eduyun.cn/v1/resources/combine/search` 使用 `sdp-app-id` 标识应用，当前可在无 `Authorization: MAC ...` 的情况下低频返回搜索候选。`Authorization` 或 `x-nd-auth` 如需用于详情或私有文件下载，只能通过运行环境临时注入。

## 栏目画像输出

```json
{
  "catalog_profile_schema": "smartedu-catalog-profile/v1",
  "source_skill": "smartedu-resources",
  "catalogs": [],
  "summary": {
    "catalogs": 0,
    "resource_catalogs": 0,
    "external_catalogs": 0
  }
}
```

## 栏目路由图

`route-map` 输出 `smartedu-route-map/v1`，用于把栏目配置转为后续扫描和详情追踪的执行线索。

```json
{
  "route_map_schema": "smartedu-route-map/v1",
  "source_skill": "smartedu-resources",
  "routes": [
    {
      "title": "精品课",
      "catalog": "syncClassroom",
      "sub_catalog": "course",
      "type": "qualityCourse",
      "page_url": "https://basic.smartedu.cn/syncClassroom?subCatalog=course",
      "scan_strategy": "search_then_detail",
      "search_tab_code": "qualityCourse",
      "detail_url_templates": []
    }
  ],
  "summary": {
    "routes": 0,
    "internal_adapter_routes": 0,
    "search_then_detail_routes": 0
  }
}
```

`scan_strategy=internal_adapter` 表示该栏目暂时由内部兼容适配器处理；`search_then_detail` 表示先通过搜索或列表接口拿资源 ID，再抓详情 JSON 并解析 `ti_items`。

## 页面画像

`page-profile` 输出 `smartedu-page-profile/v1`，用于分析 SmartEdu 页面 HTML/JS 中暴露的接口、详情页和资源链接线索。

```json
{
  "page_profile_schema": "smartedu-page-profile/v1",
  "source_skill": "smartedu-resources",
  "page_url": "https://basic.smartedu.cn/",
  "page_type": "spa_route_page",
  "api_hints": [],
  "detail_hints": [],
  "resource_link_hints": [],
  "recommended_next_actions": [],
  "summary": {
    "api_hints": 0,
    "detail_hints": 0,
    "resource_link_hints": 0,
    "auth_context": false
  }
}
```

## 栏目扫描

`scan-catalog` 输出 `smartedu-catalog-scan/v1`，用于按 `route-map` 中的一条或多条栏目路由发现资源候选。

```json
{
  "scan_schema": "smartedu-catalog-scan/v1",
  "source_skill": "smartedu-resources",
  "routes": [
    {
      "route": {},
      "status": "ok",
      "query": "",
      "online": false,
      "endpoint": "",
      "search_items_seen": 0,
      "candidates": [],
      "detail_failures": []
    }
  ],
  "candidates": [],
  "summary": {
    "routes_selected": 0,
    "routes_scanned": 0,
    "candidates": 0,
    "search_items_seen": 0,
    "online": false,
    "auth_context": false
  }
}
```

扫描候选仍是 `learning-resource-candidate/v1`；候选 `raw.smartedu_route_id`、`raw.smartedu_route_title` 和 `raw.smartedu_scan_strategy` 用于追踪来源栏目。

## 站点扫描

`scan-site` 输出 `smartedu-site-scan/v1`，用于按 `route-map` 批量扫描多个栏目，并汇总站点级候选索引。

```json
{
  "site_scan_schema": "smartedu-site-scan/v1",
  "source_skill": "smartedu-resources",
  "routes": [],
  "candidates": [],
  "failures": [],
  "summary": {
    "routes_selected": 0,
    "routes_scanned": 0,
    "routes_failed": 0,
    "internal_adapter_routes_skipped": 0,
    "raw_candidates": 0,
    "duplicates_removed": 0,
    "candidates": 0,
    "search_items_seen": 0,
    "online": false,
    "auth_context": false
  }
}
```

`scan-site` 不下载资源；它只发现候选、去重、保留栏目追踪信息，并记录失败 route。下载仍交给 downloader 或专门下载团队。

## 全站索引

`site-index` 输出 `smartedu-site-index/v1`，用于沉淀 SmartEdu 全站 route 覆盖、扫描计划和可选候选摘要。它可以只基于 `route-map` 生成离线覆盖索引，也可以通过 `--site-scan-json` 合并 `scan-site` 的候选和失败记录。

```json
{
  "site_index_schema": "smartedu-site-index/v1",
  "source_skill": "smartedu-resources",
  "source_name": "国家中小学智慧教育平台",
  "site_url": "https://basic.smartedu.cn/",
  "routes": [],
  "scan_plan": [],
  "coverage": {
    "catalogs": {},
    "sub_catalogs": {},
    "types": {},
    "resource_families": {},
    "scan_strategies": {},
    "search_tab_codes": {},
    "supported_commands": {}
  },
  "candidates": [],
  "failures": [],
  "scan_summary": {},
  "summary": {
    "routes": 0,
    "search_then_detail_routes": 0,
    "internal_adapter_routes": 0,
    "runtime_validation_routes": 0,
    "candidates": 0,
    "failures": 0,
    "route_scan_summary": {},
    "auth_context": false
  }
}
```

`scan_plan` 是给总控或后续批处理使用的轻量执行计划；`routes` 保留完整 route 原始上下文。`coverage` 用于判断当前 SmartEdu source 是否覆盖全站栏目、有哪些扫描策略、哪些 tab code 和命令能力仍需真实运行时验证。

## 详情探测

`detail-probe` 输出 `smartedu-detail-probe/v1`，用于在下载前判断搜索候选能否展开详情 JSON 和 `ti_items`。它不下载文件，只记录详情 URL 尝试、HTTP 状态、详情状态分类和脱敏错误。

```json
{
  "detail_probe_schema": "smartedu-detail-probe/v1",
  "source_skill": "smartedu-resources",
  "query": "三年级数学",
  "online_search": false,
  "search_endpoint": "sample-search-response.json",
  "probes": [
    {
      "resource_id": "qc-math-001",
      "title": "小学数学 三年级 上册 分数的初步认识",
      "catalog": "qualityCourse",
      "sub_catalog": "course",
      "content_type": "NDR_NationalLesson",
      "detail_page": "https://basic.smartedu.cn/qualityCourse/detail?...",
      "detail_endpoint_family": "s-file-ndrv2-details",
      "detail_status": "ok_with_file_items",
      "detail_access_policy": "public_detail",
      "attempts": [],
      "file_item_count": 3,
      "parsed_candidate_count": 3,
      "error": ""
    }
  ],
  "summary": {
    "search_items_seen": 1,
    "probes": 1,
    "status_counts": {"ok_with_file_items": 1},
    "access_policy_counts": {"public_detail": 1},
    "details_accessible": 1,
    "requires_auth": 0,
    "file_items": 3,
    "parsed_candidates": 3,
    "auth_context": false
  }
}
```

`detail_status` 当前分类：

- `ok_with_file_items`：详情 JSON 可取且包含 `ti_items`。
- `ok_no_file_items`：详情 JSON 可取，但没有文件项。
- `requires_auth`：详情接口返回 403，需要账号态、cookie、Authorization 或浏览器会话。
- `not_found`：详情接口返回 404，可能是模板不匹配或资源不存在。
- `detail_not_found_in_dir`：离线模式下本地详情目录没有对应 JSON。
- `missing_resource_id`：搜索候选缺少可用于详情接口的资源 ID。
- `request_failed` / `invalid_json` / `unknown`：运行时请求或响应解析失败，需要进一步联调。

## 浏览器会话摘要

`smartedu_browser_session.py export-context` 和 `check` 输出 `smartedu-browser-session/v1`，用于把浏览器登录态能力以脱敏方式传给后续流程。原始 Playwright storage state 只能保存在工作目录，不进入 git、skill 包或候选 JSON。

```json
{
  "browser_session_schema": "smartedu-browser-session/v1",
  "state_file": ".learning-resource-work/smartedu-browser/state.json",
  "state_file_exists": true,
  "auth_context": true,
  "has_cookie": true,
  "cookie_count": 3,
  "cookie_domains": ["basic.smartedu.cn"],
  "smartedu_cookie_domains": ["basic.smartedu.cn"],
  "local_storage_origins": ["https://basic.smartedu.cn"],
  "capabilities": {
    "can_use_browser_state": true,
    "can_fetch_detail": null,
    "can_probe_private_ndr": null
  },
  "secret_redaction": "不输出 cookie、Authorization、MAC、x-nd-auth 或浏览器 state 原文。"
}
```

`smartedu_browser_session.py request` 输出 `smartedu-browser-request/v1`，只保留状态、内容类型、脱敏响应头和可选 JSON 摘要：

```json
{
  "browser_request_schema": "smartedu-browser-request/v1",
  "method": "GET",
  "url": "https://s-file-1.ykt.cbern.com.cn/...",
  "auth_context": true,
  "response": {
    "ok": true,
    "status": 200,
    "content_type": "application/json",
    "headers": {"content-type": "application/json"},
    "has_json": true,
    "json_keys": ["id", "ti_items", "title"]
  }
}
```

教材候选仍使用 `learning-resource-candidate/v1`，对外来源保持：

```json
{
  "source_skill": "smartedu-resources",
  "resource_family": "教材",
  "internal_adapter": "tchMaterial",
  "candidates": [
    {
      "source": "smartedu-resources",
      "resource_type": "教材",
      "format": "pdf",
      "raw": {
        "internal_adapter": "tchMaterial",
        "smartedu_catalog": "tchMaterial"
      }
    }
  ]
}
```

这表示教材是 SmartEdu 站内资源分支，不是外部独立资源站来源。

## 资源类型映射

- `m3u8`、`mp4`、`video/*` -> `视频`
- `mp3`、`wav`、`m4a`、`audio/*` -> `音频`
- `pdf` -> `文档`
- `ppt`、`pptx` -> `课件`
- `doc`、`docx`、`txt` -> `文档`
- `jpg`、`png`、`webp`、`image/*` -> `图片`
- `zip`、`rar`、`7z` -> `压缩包`

## 访问限制

如果 `custom_properties.identification=true`，或 URL 位于 `r*-ndr-private.ykt.cbern.com.cn`，候选应标记：

```json
{
  "requires_auth": true,
  "raw": {
    "warnings": ["可能需要 SmartEdu 登录授权"]
  }
}
```
