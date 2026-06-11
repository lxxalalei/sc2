# 结构化任务输出契约

本契约用于把用户自然语言需求转换成后续 source skill、ranker、downloader 可以消费的任务对象。

## 顶层结构

```json
{
  "intent_schema": "learning-resource-intent/v1",
  "status": "ready | needs_clarification | rejected",
  "intent_type": "topic_resource | local_lookup | broad_exploration | exact_resource | unsupported",
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
  "request_scope": "candidate_set | full_coverage | exact",
  "coverage_targets": [],
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

- `topic_resource`：围绕学习主题找资料，例如四则运算、恐龙百科、唐诗启蒙。
- `local_lookup`：优先查询本地资料库。
- `broad_exploration`：主题很宽，但用户是“看看/了解/推荐”而非直接下载。
- `exact_resource`：用户指定了 URL、明确资源名称，或提供了足以唯一定位某个具体资源的一组条件。版本、年级、学科本身只是筛选条件，不应单独触发精确资源。
- `unsupported`：不属于本项目资源范围。

## execution_tasks

`execution_tasks` 是后续流程真正消费的任务列表。`status=ready` 时至少输出 1 个任务；`needs_clarification` 时必须为空。

```json
{
  "task_id": "task_001",
  "task_type": "source_search | local_search | candidate_list | direct_download",
  "target_skill": "smartedu-resources | web-learning-search | local-library-search",
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
- `task_type`：搜索候选用 `source_search`，查本地用 `local_search`，只列候选用 `candidate_list`，极明确下载用 `direct_download`。
- `target_skill`：只写来源或检索 skill，不写 ranker/downloader。
- `query`：适合来源搜索的中文搜索句，不要直接复制用户模糊原话。
- `filters`：结构化筛选条件，字段名优先沿用顶层槽位。
- `download_policy`：
  - `never`：只查询，不下载。
  - `after_user_selection`：必须先展示候选并让用户确认。
  - `direct_if_exact`：精确资源可以直接下载，但仍应由下载 skill 校验唯一性和来源。
- `ranking_hints`：给 ranker 的偏好，例如 `authority_weight`、`age_fit_required`、`printable_required`。

## request_scope

`request_scope` 描述用户希望覆盖的范围，不绑定任何具体来源或教材结构：

- `candidate_set`：找一些候选、推荐、先看看，默认值。
- `full_coverage`：用户说全部、全套、整套、所有、完整、合集、都要或都下载。
- `exact`：用户给出 URL、明确资源名或唯一定位条件。

`coverage_targets` 用于描述完整覆盖的资源面向，例如：

- `resource_set`：泛指资料/资源/材料。
- `video`：课程、视频、网课。
- `courseware`：课件、PPT。
- `practice`：习题、练习、作业、试卷。
- `audio`：音频、儿歌、听赏材料。
- `image_or_article`：图片、图文、绘本、百科文章。

`full_coverage` 不表示可以直接下载所有结果。除非来源、主题和数量都足够清楚，后续流程仍应先搜索、评分、展示覆盖计划或候选清单，再由用户确认。

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

`smartedu-resources` 是国家中小学智慧教育平台资源总入口，适合教材、课程教学、备课资源、精品课、习题、试卷、实验教学、德育、家庭教育、课后服务、专题、图片、音频、视频等官方资源。教材是 resources 的一部分，其中 `tchMaterial` 教材 PDF 是站内教材资源分支，外部仍统一路由到 `smartedu-resources`。

如果项目已有本地资料库外部索引，通常应先生成一个 `local-library-search` 任务，让 agent 检查本地是否已有可用资源。该任务不替代外部搜索；本地无命中或质量不足时，继续执行其他 source tasks。

例如用户请求“给 8 岁孩子找四则混合运算可打印练习题”时，可以同时生成：

```json
[
  {
    "task_id": "task_000",
    "task_type": "local_search",
    "target_skill": "local-library-search",
    "action": "search",
    "query": "8岁 四则混合运算 可打印练习题",
    "filters": {"learner_age": 8, "subject": "数学", "core_topic": "四则混合运算", "resource_types": ["习题"], "format_preferences": ["pdf"]},
    "download_policy": "never"
  },
  {
    "task_id": "task_001",
    "task_type": "source_search",
    "target_skill": "web-learning-search",
    "action": "search",
    "query": "8岁 四则混合运算 可打印练习题 PDF",
    "filters": {"learner_age": 8, "subject": "数学", "core_topic": "四则混合运算", "resource_types": ["习题"], "format_preferences": ["pdf"]},
    "download_policy": "after_user_selection"
  }
]
```

当前 `smartedu-resources` 是已实现的 SmartEdu 官方资源总入口之一。后续新增出版社官网、地方教育平台、音视频、百科或本地资料库来源后，应同样作为候选来源加入任务列表。

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
