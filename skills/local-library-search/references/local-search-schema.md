# 本地资料库候选输出契约

`local-library-search` 输出 `learning-resource-candidate/v1`。

## 顶层结构

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "local-library-search",
  "query": "",
  "filters": {},
  "index_file": "",
  "searched_at": "",
  "candidates": []
}
```

## 候选字段

```json
{
  "source": "local-library-search",
  "source_name": "本地学习资料库",
  "source_url": "",
  "resource_id": "",
  "title": "",
  "description": "",
  "resource_type": "",
  "format": "",
  "stage": "",
  "grade": "",
  "subject": "",
  "learning_domain": "",
  "version": "",
  "volume": null,
  "topic": "",
  "provider": "",
  "official": false,
  "downloadable": true,
  "requires_auth": false,
  "size": 0,
  "metadata_confidence": 0.0,
  "local_file": "",
  "raw": {
    "match_score": 0.0,
    "match_reasons": [],
    "warnings": [],
    "index_resource": {}
  }
}
```

## 说明

- `source_url` 保留原始来源 URL；没有来源 URL 时为空字符串。
- `local_file` 指向最终资料库中的真实资源文件。
- `downloadable=true` 表示本地文件已可直接使用，不表示需要下载。
- `requires_auth=false`，因为本地资源无需站点授权。
- `raw.match_score` 只是本地检索匹配分，不替代 ranker 的最终质量评分。
