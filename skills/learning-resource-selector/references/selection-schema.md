# 学习资源选择输出契约

## 顶层结构

```json
{
  "selection_schema": "learning-resource-selection/v1",
  "status": "awaiting_user_selection | no_suitable_options",
  "total_ranked": 0,
  "shown_count": 0,
  "hidden_count": 0,
  "options": [],
  "hidden_options": [],
  "user_message": "",
  "next_action": ""
}
```

## options

```json
{
  "option_id": "A",
  "rank": 1,
  "title": "",
  "source_name": "",
  "source_url": "",
  "resource_id": "",
  "resource_type": "",
  "format": "",
  "quality_level": "high",
  "score": 81.0,
  "recommendation": "recommended",
  "downloadable": true,
  "requires_auth": false,
  "official": false,
  "summary": "",
  "reasons": [],
  "warnings": [],
  "candidate": {}
}
```

## hidden_options

隐藏项包括：

- `low`
- `reject`
- 明显不适合用户需求的资源
- 风险较高资源

隐藏项保留原始候选，方便调试和后续重新排序。

## status

- `awaiting_user_selection`：有可展示选项，等待用户选择。
- `no_suitable_options`：没有足够合适的资源，应回到需求澄清或重新搜索。
