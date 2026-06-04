---
name: learning-resource-intent
description: 在搜索或下载前理解、澄清并结构化 3-12 岁儿童学习资源需求。用户或家长请求学习资料、启蒙内容、教材、练习、百科、唐诗宋词、儿歌、视频、图片、课件、游戏化学习材料等资源时使用，尤其适用于“四则整数运算资料”“儿童百科”“唐诗宋词启蒙”“找点适合 5 岁孩子的资料”等主题不够明确的需求。
---

# 学习资源需求理解

## 目标

将家长或儿童提出的自然语言学习需求转换为结构化学习主题与搜索计划。核心不是先判断教材版本，而是先澄清“孩子是谁、要学什么、为了什么学、需要什么形式的资源”。

本 skill 不负责搜索、评分、下载或归档文件，只负责为来源类 skill 和评分流程准备结构化需求。

## 主题优先原则

优先围绕“学习主题”分析需求，而不是围绕“教材”分析需求。

用户可能提出：

- 学科主题：四则整数运算、拼音、英语自然拼读、科学实验。
- 通识主题：儿童百科、恐龙、宇宙、人体、动物、植物。
- 语言文化：唐诗宋词、成语故事、儿歌、绘本、识字。
- 能力训练：专注力、逻辑思维、阅读理解、表达能力。
- 场景需求：亲子共读、睡前听、寒暑假学习、幼小衔接、预习复习。

只有用户明确请求教材、教科书、课本、课内同步资料时，才把版本、册次、出版社作为关键槽位。

## 输出结构

当需求足够明确，或需要制定搜索计划时，输出结构化 JSON。完整字段契约见 `references/task-schema.md`；维护或测试本 skill 时必须优先遵守该契约。

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

未知的单值字段使用 `null`，未知的列表字段使用 `[]`。

`status=ready` 时，`execution_tasks` 至少包含 1 个可执行任务；`status=needs_clarification` 时，`execution_tasks` 必须为空，并给出 1-3 个追问；`status=rejected` 用于非学习资源或不适合处理的请求。

## 槽位抽取

优先抽取这些通用槽位：

- `learner_age`：3 岁到 12 岁；如用户说“5 岁孩子”，填 `5`。
- `stage`：学前、小学低年级、小学中年级、小学高年级、小学、初中等。
- `grade`：一年级、三年级等；只有用户提供年级时填写。
- `learner_profile`：零基础、基础薄弱、进阶、兴趣启蒙、备考、亲子共读等。
- `learning_domain`：数学、语文、英语、科学、百科、文学、音乐、艺术、综合素养等。
- `subject`：更贴近学校学科时填写，如 数学、语文、英语、科学。
- `core_topic`：核心学习主题，如 四则整数运算、儿童百科、唐诗宋词、儿歌。
- `subtopics`：更细的主题，如 加减乘除混合运算、李白、恐龙、太阳系。
- `resource_goal`：启蒙、预习、复习、练习、拓展、阅读、听赏、备课、查阅。
- `resource_types`：教材、课件、习题、试卷、视频、音频、图片、绘本、百科文章、游戏、教案、素材、讲义等。
- `difficulty`：启蒙、基础、同步、提高、竞赛、适龄未知等。
- `format_preferences`：PDF、DOC/DOCX、PPT/PPTX、图片、音频、视频、网页、压缩包等。
- `source_preferences`：官方、国家平台、出版社、公开视频、儿童友好、本地资料库等。

教材类附加槽位：

- `version`：人教版、统编版、北师大版、苏教版、外研版等。
- `volume`：上册、下册、全一册、必修等。

## 常见表达映射

- “四则整数运算” -> `learning_domain: "数学"`, `core_topic: "四则整数运算"`
- “儿童百科” -> `learning_domain: "百科"`, `resource_goal: "拓展"`
- “唐诗宋词” -> `learning_domain: "文学"`, `core_topic: "唐诗宋词"`
- “儿歌” -> `learning_domain: "音乐"`, `resource_types: ["音频", "视频", "歌词"]`
- “课本/电子教材/教科书” -> `resource_types: ["教材"]`
- “PPT/课件/课堂用” -> `resource_types: ["课件"]`, `format_preferences: ["ppt"]`
- “练一练/题/作业/巩固” -> `resource_types: ["习题"]`
- “讲解/网课/视频” -> `resource_types: ["视频"]`
- “老师用/上课用” -> `resource_goal: "备课"`
- “孩子自学/预习” -> `resource_goal: "预习"`
- “亲子共读/睡前” -> `resource_goal: "阅读"` 或 `听赏`

## 可执行任务规则

`execution_tasks` 是本 skill 的核心交付物。它不是自然语言建议，而是后续搜索、评分、下载流程的输入。

任务必须说明：

- `task_type`：`source_search`、`local_search`、`candidate_list` 或 `direct_download`。
- `target_skill`：应调用的来源或检索 skill。
- `action`：`search`、`list-only` 或 `download`。
- `query`：为搜索生成的规范中文查询句。
- `filters`：结构化筛选条件。
- `download_policy`：`never`、`after_user_selection` 或 `direct_if_exact`。
- `ranking_hints`：给评分环节的偏好。

除非用户请求非常精确且来源明确，否则下载策略默认使用 `after_user_selection`。不要因为用户说“都下载”就跳过候选展示和评分。

## 澄清规则

不要把每个缺失槽位都视为阻塞。只有缺失信息会导致搜索范围过大、结果质量差、年龄不适配或下载风险较高时，才向用户追问。

优先澄清这些问题：

1. 孩子年龄或年级。
2. 核心学习主题。
3. 学习目标或使用场景。
4. 资源类型或格式。
5. 是否要课内同步，若是再问版本和册次。

通常需要先追问的情况：

- 主题过宽，例如“儿童百科”“数学资料”“唐诗宋词资料”。
- 没有年龄/年级，且资源适龄性很重要。
- 用户要求“下载”，但没有说明要视频、音频、文档还是练习。
- 用户明确要课内同步或教材，但缺少年级、版本、册次。

可以先搜索或列候选的情况：

- 用户说“有哪些/先看看/帮我找找”。
- 已有年龄/年级 + 主题，足以生成候选清单。
- 用户明确说“全部/都要”，且结果数量可控。
- 用户只需要泛读或百科拓展，版本和册次不重要。

追问要简短，一次最多问 1-3 个问题。不要一次问完所有槽位。

## 澄清示例

更多覆盖用例见 `references/test-cases.md`。维护本 skill 时，优先用这些样例检查是否仍能稳定判断“追问还是搜索”，以及能否生成 `execution_tasks` 和 `ranking_profile`。

用户：“我要四则整数运算的学习资料”

```json
{
  "status": "needs_clarification",
  "learning_domain": "数学",
  "core_topic": "四则整数运算",
  "missing_slots": ["learner_age_or_grade", "resource_goal", "resource_types"],
  "clarifying_questions": ["孩子大概几岁或几年级？", "你想要讲解资料、练习题，还是视频？"]
}
```

用户：“找点儿童百科”

```json
{
  "status": "needs_clarification",
  "learning_domain": "百科",
  "core_topic": "儿童百科",
  "resource_goal": "拓展",
  "missing_slots": ["learner_age", "subtopics", "resource_types"],
  "clarifying_questions": ["孩子几岁？", "更想看动物、恐龙、宇宙、人体，还是综合百科？", "需要图文、视频还是音频？"]
}
```

用户：“给 5 岁孩子找唐诗宋词启蒙音频”

```json
{
  "status": "ready",
  "learner_age": 5,
  "stage": "学前",
  "learning_domain": "文学",
  "core_topic": "唐诗宋词启蒙",
  "resource_goal": "听赏",
  "resource_types": ["音频"],
  "difficulty": "启蒙",
  "execution_tasks": [
    {
      "task_id": "task_001",
      "task_type": "source_search",
      "target_skill": "web-learning-search",
      "action": "search",
      "query": "5岁 唐诗宋词启蒙 音频 儿童",
      "filters": {"learner_age": 5, "core_topic": "唐诗宋词启蒙", "resource_types": ["音频"]},
      "download_policy": "after_user_selection"
    }
  ]
}
```

用户：“先看看小学三年级数学教材有哪些”

```json
{
  "status": "ready",
  "stage": "小学",
  "grade": "三年级",
  "learning_domain": "数学",
  "subject": "数学",
  "resource_types": ["教材"],
  "execution_tasks": [
    {
      "task_id": "task_001",
      "task_type": "candidate_list",
      "target_skill": "smartedu-textbooks",
      "action": "list-only",
      "query": "小学三年级数学教材",
      "filters": {"stage": "小学", "grade": "三年级", "subject": "数学"},
      "download_policy": "never"
    }
  ]
}
```

用户：“下载人教版小学三年级数学上册”

```json
{
  "status": "ready",
  "stage": "小学",
  "grade": "三年级",
  "learning_domain": "数学",
  "subject": "数学",
  "version": "人教版",
  "volume": "上册",
  "resource_types": ["教材"],
  "execution_tasks": [
    {
      "task_id": "task_001",
      "task_type": "direct_download",
      "target_skill": "smartedu-textbooks",
      "action": "download",
      "query": "人教版小学三年级数学上册教材",
      "filters": {"stage": "小学", "grade": "三年级", "subject": "数学", "version": "人教版", "volume": "上册"},
      "download_policy": "direct_if_exact"
    }
  ]
}
```

## 搜索计划规则

为每个可能的来源 skill 创建一个 `execution_tasks` 项：

- 已有精确来源 skill 且与用户需求匹配时，可加入候选来源任务。
- 用户需求未指定来源或可能存在多个来源时，应保留通用搜索结果标准化任务。
- 用户要求查询已有资料时，可加入本地资料库检索任务。
- 后续新增的来源 skill 应按同一规则加入候选任务，不需要修改全局理解逻辑。

来源 skill 只接收抽取后的筛选条件和规范查询句，不接收完整对话。

来源选择只决定去哪找候选，不决定最终推荐。多个来源返回的候选必须统一交给 analyzer、ranker、selector。

## 回复规则

如果 `status` 为 `needs_clarification`，用自然语言询问 `clarifying_questions`，不要继续搜索或下载。

如果 `status` 为 `ready`，将 `execution_tasks` 交给来源类 skill，继续后续工作流。
