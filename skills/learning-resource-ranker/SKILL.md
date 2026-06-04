---
name: learning-resource-ranker
description: 对学习资源候选列表进行质量评分、排序并解释推荐理由。用户或工作流已经完成资源搜索，拿到教材、习题、课件、视频、音频、图片、网页等候选资源后，使用本 skill 判断哪些资源更适合 3-12 岁儿童与家长的学习需求。
---

# 学习资源质量评分

## 目标

根据 `learning-resource-intent` 输出的结构化需求、`ranking_profile` 和 source skill 返回的候选资源，对候选资源进行统一评分、排序和风险提示。

本 skill 不负责搜索、下载或归档。它只回答：哪些候选资源更值得展示给用户，为什么。

## 输入

优先接收如下数据：

```json
{
  "intent_schema": "learning-resource-intent/v1",
  "intent": {},
  "ranking_profile": {},
  "candidate_schema": "learning-resource-candidate/v1",
  "candidates": []
}
```

如果上游没有完整 `intent`，也可以只接收候选资源列表，但评分置信度应降低。

如果 source skill 输出中包含 `filters` 但没有 `intent`，可将 `filters` 作为简化意图参与评分，例如 `smartedu-textbooks --list-only` 的输出。

候选资源字段优先兼容：

- `title`
- `source`
- `source_name`
- `source_url`
- `resource_id`
- `resource_type`
- `format`
- `stage`
- `grade`
- `subject`
- `learning_domain`
- `topic`
- `version`
- `volume`
- `provider`
- `official`
- `downloadable`
- `requires_auth`
- `size`
- `metadata_confidence`
- `raw`

如果候选经过 `learning-resource-analyzer`，应读取 `raw.analysis.text_sample`、`raw.analysis.keywords`、`raw.analysis.warnings` 和 `raw.analysis.analysis_confidence` 作为评分证据。

## 输出

输出结构见 `references/ranking-schema.md`。

核心结构：

```json
{
  "ranking_schema": "learning-resource-ranking/v1",
  "ranked_candidates": [
    {
      "rank": 1,
      "final_score": 86.0,
      "quality_level": "high",
      "recommendation": "recommended",
      "score_breakdown": {},
      "reasons": [],
      "warnings": [],
      "candidate": {}
    }
  ]
}
```

## 评分维度

默认按 100 分制评分：

- `relevance` 主题匹配：30 分。
- `age_fit` 年龄/阶段/年级匹配：20 分。
- `authority` 来源权威性：15 分。
- `accessibility` 可访问与可下载性：10 分。
- `format_fit` 格式适配：10 分。
- `safety` 儿童友好与来源风险：10 分。
- `metadata_quality` 元数据完整度：5 分。

如果输入包含 `ranking_profile.weights`，可以按权重调整，但必须保持可解释，不要让单一维度完全压过安全性和相关性。

## 评分原则

- 相关性不足时，即使来源权威也不能高分。
- 年龄或年级不匹配时，应明显降权。
- 官方来源、出版社、国家平台通常加权，但不等于一定排第一。
- 可直接访问、格式符合用户场景的资源优先。
- 需要登录、token 或授权访问的资源可以保留，但应提示。
- 来源不明、诱导安装下载器、标题夸张、疑似成人化或无关内容，应降权或排除。
- 用户要求下载时，评分结果仍应先交给用户选择，除非上游任务是精确教材且 `download_policy=direct_if_exact`。

## 质量等级

- `excellent`：90-100，强推荐。
- `high`：75-89，推荐。
- `medium`：60-74，可作为备选。
- `low`：40-59，不优先。
- `reject`：低于 40 或明显不适合，不建议展示或下载。

## 使用脚本

可用内置脚本进行确定性评分：

```bash
python3 skills/learning-resource-ranker/scripts/rank_candidates.py input.json
```

也可以从标准输入读取：

```bash
python3 skills/learning-resource-ranker/scripts/rank_candidates.py - < input.json
```

脚本输出 `learning-resource-ranking/v1` JSON。详细输入输出和测试样例见：

- `references/ranking-schema.md`
- `references/test-cases.md`

## 回复规则

给用户展示结果时，不要只报分数。至少说明：

1. 推荐顺序。
2. 每个候选为什么适合。
3. 有哪些访问、格式、适龄或来源风险。
4. 是否建议下载，或是否需要用户确认。
