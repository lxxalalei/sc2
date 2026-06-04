# 通用网页候选资源格式

`web-learning-search` 输出 `learning-resource-candidate/v1`。

## 顶层结构

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "web-learning-search",
  "query": "",
  "filters": {},
  "searched_at": "",
  "candidates": []
}
```

## 候选字段

```json
{
  "source": "web-learning-search",
  "source_name": "",
  "source_url": "",
  "resource_id": "",
  "title": "",
  "description": "",
  "resource_type": "",
  "format": "",
  "stage": null,
  "grade": null,
  "subject": null,
  "learning_domain": null,
  "version": null,
  "volume": null,
  "topic": null,
  "provider": "",
  "official": false,
  "downloadable": false,
  "requires_auth": false,
  "size": null,
  "metadata_confidence": 0.0,
  "raw": {
    "rank": 1,
    "snippet": "",
    "host": "",
    "warnings": []
  }
}
```

## 字段原则

- `source_url` 必须是候选页面或文件 URL。
- `resource_id` 可使用 URL hash，保证同一 URL 稳定。
- `official` 仅在能从域名或来源名明确判断时为 `true`。
- `downloadable` 只表示链接看起来指向可下载文件，不代表已经下载成功。
- `requires_auth` 不确定时为 `false`，但可在 `raw.warnings` 中标注可疑登录限制。
- `metadata_confidence` 只衡量标题、摘要、格式、类型等元数据完整度，不代表资源质量。
