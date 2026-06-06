# 资源站发现输出契约

## 顶层结构

```json
{
  "source_discovery_schema": "learning-resource-source-discovery/v1",
  "query": "",
  "filters": {},
  "discovered_at": "",
  "sources": [],
  "rejected_sources": [],
  "summary": {
    "input": 0,
    "sources": 0,
    "rejected": 0,
    "known_sources": 0,
    "profile_candidates": 0
  }
}
```

## sources

```json
{
  "source_id": "",
  "source_url": "",
  "host": "",
  "title": "",
  "description": "",
  "source_type": "known_source | resource_site | resource_page | video_page | article_page | unknown",
  "source_score": 0.0,
  "authority_score": 0.0,
  "resource_density_score": 0.0,
  "accessibility_score": 0.0,
  "risk_score": 0.0,
  "known_skill": "",
  "next_action": "use_known_source_skill | profile_site | extract_direct_candidates | keep_as_web_candidate",
  "resource_format_hints": ["pdf"],
  "resource_type_hints": ["习题"],
  "reasons": [],
  "warnings": [],
  "raw": {}
}
```

## rejected_sources

```json
{
  "source_id": "",
  "source_url": "",
  "host": "",
  "title": "",
  "source_type": "download_risk",
  "source_score": 0.0,
  "next_action": "reject",
  "warnings": []
}
```

## 分数含义

- `source_score`：是否值得继续分析该来源，不代表具体资源质量。
- `authority_score`：来源可信度。
- `resource_density_score`：页面或站点像不像资源密集来源。
- `accessibility_score`：是否看起来可访问、可抽取。
- `risk_score`：风险越高分越低。
