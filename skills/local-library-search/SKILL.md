---
name: local-library-search
description: 基于学习资料库外部索引检索本地已有学习资源，并输出 learning-resource-candidate/v1 候选。用于用户查找学习资料时优先检查本地资料库，避免重复联网搜索和重复下载；不负责评分、下载、归档或修改资料库文件。
---

# 本地学习资料库检索

## 目标

读取 `learning-library-index` 维护的外部 `resources.json`，按用户需求或结构化任务检索本地已有学习资源，并输出标准候选列表。

本 skill 是 source skill：

- 不搜索互联网。
- 不评分、不排序最终推荐。
- 不下载、不归档、不修改资料库文件。
- 不写入最终资料库。
- 不把某类资源固定绑定到本地来源；本地结果只是候选来源之一。

## 输入

优先接收 `learning-resource-intent` 的 `execution_tasks` 中目标为 `local-library-search` 的任务：

```json
{
  "task_id": "task_001",
  "target_skill": "local-library-search",
  "action": "search",
  "query": "8岁 四则混合运算 练习题",
  "filters": {
    "learner_age": 8,
    "subject": "数学",
    "core_topic": "四则混合运算",
    "resource_types": ["习题"],
    "format_preferences": ["PDF"]
  }
}
```

也可以接收简化 JSON：

```json
{
  "query": "唐诗启蒙音频",
  "filters": {"learning_domain": "文学", "resource_types": ["音频"]}
}
```

## 输出

输出 `learning-resource-candidate/v1`：

```json
{
  "candidate_schema": "learning-resource-candidate/v1",
  "source_skill": "local-library-search",
  "query": "",
  "filters": {},
  "candidates": []
}
```

候选会包含 `local_file`，指向最终资料库中的真实资源文件。

## 使用脚本

```bash
python3 skills/local-library-search/scripts/search_local_library.py \
  --task-json task.json \
  --index-file .learning-resource-work/index/resources.json \
  --limit 10
```

直接按查询词检索：

```bash
python3 skills/local-library-search/scripts/search_local_library.py \
  --query "四则混合运算 练习题" \
  --index-file .learning-resource-work/index/resources.json
```

输出文件：

```bash
python3 skills/local-library-search/scripts/search_local_library.py \
  --task-json task.json \
  -o .learning-resource-work/local-candidates.json
```

## 匹配规则

第一版使用启发式匹配：

- 标题、主题、学科、资源类型、来源、格式命中加分。
- `query` 词命中越多，相关性越高。
- `filters` 中的学段、年级、学科、主题、资源类型、格式偏好命中加分。
- 本地文件存在、分类置信度高、无需登录会增加元数据置信度。
- `needs_review=true` 的资源不会排除，但会在 `raw.warnings` 中标记。

检索结果仍应交给 `learning-resource-analyzer`、`learning-resource-ranker` 和 `learning-resource-selector`，不要直接作为最终推荐。

## 索引边界

- `resources.json` 必须来自资料库外部，例如 `.learning-resource-work/index/resources.json`。
- 如果索引不存在，返回空候选，不创建最终资料库文件。
- 如果索引记录的 `library_file` 不存在，默认跳过；使用 `--include-missing` 时可保留并标记风险。
