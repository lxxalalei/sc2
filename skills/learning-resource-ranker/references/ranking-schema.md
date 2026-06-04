# 学习资源评分输出契约

## 输入示例

```json
{
  "intent": {
    "learner_age": 8,
    "stage": "小学低年级",
    "subject": "数学",
    "core_topic": "四则混合运算",
    "resource_types": ["习题"],
    "format_preferences": ["PDF", "DOC/DOCX"]
  },
  "ranking_profile": {
    "primary_goal": "可打印练习",
    "must_match": ["learner_age", "core_topic"],
    "prefer": ["PDF", "可打印"],
    "avoid": ["来源不明", "强制下载器"]
  },
  "candidate_schema": "learning-resource-candidate/v1",
  "candidates": []
}
```

## 输出结构

```json
{
  "ranking_schema": "learning-resource-ranking/v1",
  "total": 0,
  "ranked_candidates": [],
  "rejected_candidates": [],
  "summary": {
    "excellent": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "reject": 0
  }
}
```

## ranked_candidates

```json
{
  "rank": 1,
  "final_score": 86.0,
  "quality_level": "high",
  "recommendation": "recommended",
  "score_breakdown": {
    "relevance": 28.0,
    "age_fit": 18.0,
    "authority": 12.0,
    "accessibility": 8.0,
    "format_fit": 8.0,
    "safety": 9.0,
    "metadata_quality": 3.0
  },
  "reasons": [
    "主题与四则混合运算匹配",
    "资源类型符合习题需求"
  ],
  "warnings": [
    "需要登录或授权访问"
  ],
  "candidate": {}
}
```

## recommendation

- `strong_recommend`：强推荐展示给用户。
- `recommended`：推荐展示给用户。
- `backup`：可以作为备选。
- `not_preferred`：不优先展示。
- `reject`：不建议展示或下载。

## rejected_candidates

明显不适合或低于展示阈值的候选放入 `rejected_candidates`。不要删除候选，保留评分和拒绝原因，方便调试搜索质量。
