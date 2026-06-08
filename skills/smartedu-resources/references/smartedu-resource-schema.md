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
