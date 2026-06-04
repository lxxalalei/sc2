# 结构化任务输出契约

本契约用于把用户自然语言需求转换成后续 source skill、ranker、downloader 可以消费的任务对象。

## 顶层结构

```json
{
  "intent_schema": "learning-resource-intent/v1",
  "status": "ready | needs_clarification | rejected",
  "intent_type": "textbook | topic_resource | local_lookup | broad_exploration | unsupported",
  "confidence": 0.0,
  "normalized_query": "",
  "learner_age": null,
  "stage": null,
  "grade": null,
  "learner_profile": null,
  "learning_domain": null,
  "subject": null,
  "core_topic": null,
  "subtopics": [],
  "resource_goal": "启蒙 | 预习 | 复习 | 练习 | 拓展 | 阅读 | 听赏 | 备课 | 查阅 | 未指定",
  "resource_types": [],
  "difficulty": null,
  "format_preferences": [],
  "source_preferences": [],
  "version": null,
  "volume": null,
  "constraints": [],
  "missing_slots": [],
  "clarifying_questions": [],
  "execution_tasks": [],
  "ranking_profile": {}
}
```

## 状态含义

- `ready`：信息足以生成候选搜索任务，可以继续调用 source skill。
- `needs_clarification`：继续搜索会明显发散、低质或高风险，必须先追问用户。
- `rejected`：请求不属于 3-12 岁学习资源，或涉及明显违法、侵权、危险内容。

## 意图类型

- `textbook`：教材、课本、教科书、课内同步资料。
- `topic_resource`：围绕学习主题找资料，例如四则运算、恐龙百科、唐诗启蒙。
- `local_lookup`：优先查询本地资料库。
- `broad_exploration`：主题很宽，但用户是“看看/了解/推荐”而非直接下载。
- `unsupported`：不属于本项目资源范围。

## execution_tasks

`execution_tasks` 是后续流程真正消费的任务列表。`status=ready` 时至少输出 1 个任务；`needs_clarification` 时必须为空。

```json
{
  "task_id": "task_001",
  "task_type": "source_search | local_search | candidate_list | direct_download",
  "target_skill": "smartedu-textbooks | web-learning-search | local-library-search",
  "action": "search | list-only | download",
  "priority": 1,
  "query": "",
  "filters": {},
  "expected_resource_types": [],
  "expected_formats": [],
  "download_policy": "never | after_user_selection | direct_if_exact",
  "ranking_hints": {}
}
```

字段要求：

- `task_id`：本次输出内唯一，使用 `task_001` 这种稳定编号。
- `task_type`：搜索候选用 `source_search`，查本地用 `local_search`，教材候选列表用 `candidate_list`，极明确下载用 `direct_download`。
- `target_skill`：只写来源或检索 skill，不写 ranker/downloader。
- `query`：适合来源搜索的中文搜索句，不要直接复制用户模糊原话。
- `filters`：结构化筛选条件，字段名优先沿用顶层槽位。
- `download_policy`：
  - `never`：只查询，不下载。
  - `after_user_selection`：必须先展示候选并让用户确认。
  - `direct_if_exact`：教材等精确资源可以直接下载，但仍应由下载 skill 校验唯一性和来源。
- `ranking_hints`：给 ranker 的偏好，例如 `authority_weight`、`age_fit_required`、`printable_required`。

## ranking_profile

`ranking_profile` 用于告诉评分 skill 本次更重视什么。

```json
{
  "primary_goal": "主题匹配 | 适龄 | 官方权威 | 可打印 | 可听赏 | 可观看 | 课内同步",
  "must_match": ["learner_age", "core_topic"],
  "prefer": ["official", "pdf", "printable"],
  "avoid": ["来源不明", "强制下载器", "成人化内容"],
  "weights": {
    "relevance": 0.3,
    "age_fit": 0.2,
    "authority": 0.15,
    "accessibility": 0.1,
    "format": 0.1,
    "safety": 0.15
  }
}
```

权重总和应接近 1.0。不确定时使用默认权重，不要为了凑字段虚构强偏好。

## 来源选择说明

`execution_tasks` 可以包含多个来源任务。不要把某一类资源永久绑定到单一来源。

例如用户请求“找小学三年级数学教材”时，可以同时生成：

```json
[
  {
    "task_id": "task_001",
    "task_type": "candidate_list",
    "target_skill": "smartedu-textbooks",
    "action": "list-only",
    "query": "小学三年级数学教材",
    "filters": {"stage": "小学", "grade": "三年级", "subject": "数学"},
    "download_policy": "never"
  },
  {
    "task_id": "task_002",
    "task_type": "source_search",
    "target_skill": "web-learning-search",
    "action": "search",
    "query": "小学三年级 数学 教材 PDF",
    "filters": {"stage": "小学", "grade": "三年级", "subject": "数学", "resource_types": ["教材"]},
    "download_policy": "after_user_selection"
  }
]
```

当前 `smartedu-textbooks` 是已实现的官方教材来源之一。后续新增出版社官网、地方教育平台或本地资料库来源后，应同样作为候选来源加入任务列表。

## 示例

用户：“给 8 岁孩子找四则混合运算练习题，最好能打印”

```json
{
  "intent_schema": "learning-resource-intent/v1",
  "status": "ready",
  "intent_type": "topic_resource",
  "confidence": 0.88,
  "normalized_query": "8 岁儿童四则混合运算可打印练习题",
  "learner_age": 8,
  "stage": "小学低年级",
  "grade": null,
  "learning_domain": "数学",
  "subject": "数学",
  "core_topic": "四则混合运算",
  "subtopics": [],
  "resource_goal": "练习",
  "resource_types": ["习题"],
  "format_preferences": ["PDF", "DOC/DOCX"],
  "source_preferences": [],
  "constraints": ["适合打印"],
  "missing_slots": [],
  "clarifying_questions": [],
  "execution_tasks": [
    {
      "task_id": "task_001",
      "task_type": "source_search",
      "target_skill": "web-learning-search",
      "action": "search",
      "priority": 1,
      "query": "8岁 四则混合运算 练习题 可打印 PDF",
      "filters": {
        "learner_age": 8,
        "subject": "数学",
        "core_topic": "四则混合运算",
        "resource_types": ["习题"],
        "printable": true
      },
      "expected_resource_types": ["习题"],
      "expected_formats": ["PDF", "DOC/DOCX"],
      "download_policy": "after_user_selection",
      "ranking_hints": {
        "age_fit_required": true,
        "printable_required": true
      }
    }
  ],
  "ranking_profile": {
    "primary_goal": "可打印练习",
    "must_match": ["learner_age", "core_topic"],
    "prefer": ["PDF", "DOC/DOCX", "可打印"],
    "avoid": ["来源不明", "强制下载器", "成人化内容"],
    "weights": {
      "relevance": 0.3,
      "age_fit": 0.25,
      "authority": 0.1,
      "accessibility": 0.1,
      "format": 0.1,
      "safety": 0.15
    }
  }
}
```
