# 资源站结构分析输出契约

## 顶层结构

```json
{
  "site_profile_schema": "site-profile/v1",
  "profiled_at": "",
  "profiles": [],
  "failures": [],
  "summary": {
    "input": 0,
    "profiled": 0,
    "failed": 0,
    "dedicated_source_recommended": 0,
    "generic_extract_recommended": 0
  }
}
```

## profiles

```json
{
  "source_id": "",
  "source_url": "",
  "host": "",
  "title": "",
  "description": "",
  "site_type": "static_resource_page | resource_listing | spa_app | media_page | article_page | unknown",
  "crawl_strategy": "generic_extract | profile_deeper | dedicated_source_skill | keep_as_web_candidate | reject",
  "score": 0.0,
  "resource_links": [
    {
      "url": "",
      "format": "pdf",
      "text": ""
    }
  ],
  "api_hints": [],
  "script_hints": [],
  "pagination_hints": [],
  "detail_link_hints": [],
  "auth_hints": [],
  "resource_format_hints": [],
  "resource_type_hints": [],
  "reasons": [],
  "warnings": [],
  "raw": {}
}
```

## failures

```json
{
  "source_url": "",
  "error": ""
}
```

## 分析说明

- `score` 表示该站是否值得继续结构化接入，不代表具体资源质量。
- `api_hints` 是从 HTML 和 JS 文本中提取的疑似接口，不保证可直接调用。
- `crawl_strategy=dedicated_source_skill` 表示应沉淀独立 source skill。
- `crawl_strategy=generic_extract` 表示后续可以由通用网页抽取器直接提取候选资源。
